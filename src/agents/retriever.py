"""Retriever agent with CRAG-style correction.

Algorithm
---------
1. For each sub-question, search FAISS for top-k chunks.
2. Deduplicate chunks across sub-questions.
3. CRAG correction: if the best relevance score < threshold, rewrite the
   query (once) using the LLM and retry.
4. Return the merged, ranked chunk list.
"""

from __future__ import annotations

import logging
import time

import config
from src import search_backend
from src.agents.state import AgentState

logger = logging.getLogger(__name__)

_REWRITE_TMPL = (
    "The query '{query}' retrieved weak results. "
    "Rewrite it as a better, more specific search query for academic papers. "
    "Return only the rewritten query string — no explanation."
)


def _load_store(corpus_id: str):
    # Vector-store seam: FAISS on disk locally, or Azure AI Search when
    # SEARCH_BACKEND=azure_search. Both expose .search(query, k).
    return search_backend.get_store(corpus_id)


def _search(store, query: str, top_k: int) -> list[dict]:
    # search returns list[RetrievalResult] with .chunk and .score
    results = store.search(query, k=top_k)
    return [
        {
            "chunk_id": r.chunk.chunk_id,
            "source": r.chunk.source,
            "page": r.chunk.page,
            "text": r.chunk.text,
            "score": float(r.score),
            "section": getattr(r.chunk, "section", ""),
        }
        for r in results
    ]


def _rewrite_query(query: str, mode: str, provider: str) -> str:
    try:
        from src.llm_backend import get_backend
        llm = get_backend(mode=mode, provider=provider)
        return llm.generate(_REWRITE_TMPL.format(query=query),
                            temperature=0.3, max_tokens=64).strip()
    except Exception:
        return query


def retriever_node(state: AgentState) -> dict:
    t0 = time.perf_counter()
    corpus_id = state["corpus_id"]
    top_k = state["top_k"]
    sub_questions = state.get("sub_questions") or [state["question"]]
    attempts = state.get("retrieval_attempts", 0)

    store = _load_store(corpus_id)
    if store is None:
        elapsed = int((time.perf_counter() - t0) * 1000)
        log = state.get("stage_log", [])
        log.append({"stage": "retriever", "error": "index not found", "latency_ms": elapsed})
        return {"chunks": [], "retrieval_attempts": attempts + 1, "stage_log": log}

    per_sq: list[list[dict]] = []

    for sq in sub_questions:
        hits = _search(store, sq, top_k=top_k)

        # CRAG correction: rewrite once if best relevance < threshold
        if hits and hits[0]["score"] < config.RETRIEVAL_RELEVANCE_THRESHOLD and attempts == 0:
            new_query = _rewrite_query(sq, state["mode"], state["provider"])
            if new_query != sq:
                logger.info("CRAG: rewriting '%s' → '%s'", sq[:60], new_query[:60])
                hits = _search(store, new_query, top_k=top_k)

        per_sq.append(hits)

    # Round-robin merge: each sub-question keeps its best-ranked chunks.
    # (A plain global-score sort lets lexically-similar but useless chunks —
    # appendix tables, metric sections — crowd out the chunk that actually
    # answers a sub-question.) Cloud mode affords a slightly larger context;
    # local (CPU) mode stays at top_k to keep prompt-processing time sane.
    cap = max(top_k, 8) if state.get("mode") != "local" else top_k
    seen: set[str] = set()
    merged: list[dict] = []
    rank = 0
    while len(merged) < cap and any(rank < len(h) for h in per_sq):
        for hits in per_sq:
            if rank < len(hits):
                h = hits[rank]
                if h["chunk_id"] not in seen:
                    seen.add(h["chunk_id"])
                    merged.append(h)
                    if len(merged) >= cap:
                        break
        rank += 1

    elapsed = int((time.perf_counter() - t0) * 1000)
    log = state.get("stage_log", [])
    log.append({
        "stage": "retriever",
        "chunks_found": len(merged),
        "top_score": merged[0]["score"] if merged else 0.0,
        "crag_triggered": attempts == 0 and bool(merged) and merged[0]["score"] < config.RETRIEVAL_RELEVANCE_THRESHOLD,
    })

    return {"chunks": merged, "retrieval_attempts": attempts + 1, "stage_log": log}

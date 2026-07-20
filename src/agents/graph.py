"""LangGraph pipeline: Planner → Retriever → Synthesizer → Verifier.

                         ┌──────────┐
              START ───► │  Planner │
                         └────┬─────┘
                              │
                         ┌────▼──────┐
                         │ Retriever │ (CRAG correction inside)
                         └────┬──────┘
                              │
                         ┌────▼───────────┐
               ┌─────── ►│  Synthesizer   │◄──┐
               │          └────┬───────────┘   │ revise
               │               │               │
               │          ┌────▼─────┐         │
               │          │ Verifier │──────────┘
               │          └────┬─────┘
               │               │ done
               └───────────── END
"""

from __future__ import annotations

import re
import time
from typing import Any

import config

_pipeline: Any = None

# ── Pipeline guards ──────────────────────────────────────────────────────────
# Small-talk / identity questions must never reach the RAG pipeline: retrieval
# returns irrelevant chunks and small local models then hallucinate freely
# (at multi-minute cost on CPU). Answer them instantly instead.
_SMALLTALK_RE = re.compile(
    r"^\s*(hi+|hello+|hey+|yo|hai|howdy|good\s+(morning|afternoon|evening)"
    r"|thanks?|thank\s+you|ok(ay)?|bye|goodbye)[\s!.,?]*$"
    r"|who\s+(are|r)\s+(you|u)\b"
    r"|what(?:'s|\s+is)\s+(?:your|ur)\s+name"
    r"|what\s+can\s+(you|u)\s+do"
    r"|how\s+are\s+(you|u)\b",
    re.IGNORECASE,
)

_SMALLTALK_ANSWER = (
    "I'm VeritasRAG — a research assistant that answers questions strictly from "
    "the PDFs in your library and verifies every citation against them. "
    "Ask me something about your uploaded papers, e.g. "
    "\"What are the limitations of standard RAG systems?\""
)

_OFFTOPIC_ANSWER = (
    "I couldn't find anything in your PDF library related to that question, "
    "so I won't guess. Try rephrasing it, or ask about a topic your uploaded "
    "papers actually cover."
)


def _pipeline_shortcut(question: str, corpus_id: str) -> tuple[str, str] | None:
    """Return ``(reason, answer)`` if the question should bypass the pipeline.

    Two cases: small-talk/identity questions, and questions whose best
    retrieval score is below ``config.OFFTOPIC_SCORE_FLOOR`` (nothing in the
    corpus is even loosely related — synthesis would only hallucinate).
    """
    q = question.strip()
    if len(q.split()) <= 8 and _SMALLTALK_RE.search(q):
        return "smalltalk", _SMALLTALK_ANSWER

    try:
        from src.retrieval import load_vector_store

        vs = load_vector_store(corpus_id)
        if vs is not None:
            hits = vs.search(q, k=3)
            best = max((h.score for h in hits), default=0.0)
            if best < config.OFFTOPIC_SCORE_FLOOR:
                return "off_topic", _OFFTOPIC_ANSWER
    except Exception:
        pass  # never let the guard break the pipeline itself
    return None


def get_pipeline() -> Any:
    """Build and compile the LangGraph pipeline once, on first use.

    Compiling lazily (rather than at import time) keeps ``import
    src.agents.graph`` cheap and side-effect-free: importers that only need
    ``run`` — or that import this module before optional deps like
    ``langgraph`` are available — no longer crash at import time.
    """
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    from langgraph.graph import END, StateGraph

    from src.agents.planner import planner_node
    from src.agents.retriever import retriever_node
    from src.agents.state import AgentState
    from src.agents.synthesizer import synthesizer_node
    from src.agents.verifier import should_revise, verifier_node

    workflow = StateGraph(AgentState)
    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("verifier", verifier_node)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "retriever")
    workflow.add_edge("retriever", "synthesizer")
    workflow.add_edge("synthesizer", "verifier")
    workflow.add_conditional_edges(
        "verifier",
        should_revise,
        {"revise": "synthesizer", "done": END},
    )

    _pipeline = workflow.compile()
    return _pipeline


def run(
    question: str,
    corpus_id: str,
    mode: str = "cloud",
    provider: str = "groq",
    top_k: int = 5,
) -> dict[str, Any]:
    """Run the full agentic RAG pipeline and return the final state."""
    t0 = time.perf_counter()
    # Offline speed: fewer chunks -> shorter prompt -> faster CPU generation.
    if (mode or "").lower() == "local":
        top_k = min(top_k, config.OFFLINE_TOP_K)
    initial: AgentState = {
        "question": question,
        "corpus_id": corpus_id,
        "mode": mode,
        "provider": provider,
        "top_k": top_k,
        "sub_questions": [],
        "chunks": [],
        "retrieval_attempts": 0,
        "answer": "",
        "claims": [],
        "overall_faithfulness": 0.0,
        "revision_count": 0,
        "verified": False,
        "latency_ms": 0,
        "stage_log": [],
        "error": None,
    }

    shortcut = _pipeline_shortcut(question, corpus_id)
    if shortcut is not None:
        reason, answer = shortcut
        elapsed = int((time.perf_counter() - t0) * 1000)
        return {
            **initial,
            "answer": answer,
            "verified": True,
            "overall_faithfulness": 1.0,
            "latency_ms": elapsed,
            "stage_log": [{"stage": "guard", "reason": reason, "latency_ms": elapsed}],
        }

    try:
        final = get_pipeline().invoke(initial)
    except Exception as exc:
        final = {**initial, "answer": f"[Pipeline error: {exc}]", "error": str(exc)}

    final["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    return final


def main() -> None:  # pragma: no cover - CLI glue
    """CLI: ``python -m src.agents.graph "question" [--corpus ID]``.

    Also reachable as ``python -m src.graph "question"`` via the thin shim in
    ``src/graph.py`` (the command documented in prompt.md §5).
    """
    import argparse
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Multi-agent RAG pipeline")
    ap.add_argument("question", help="the question to answer")
    ap.add_argument("--corpus", default="default", help="corpus id under data/corpora/")
    ap.add_argument("--mode", default="cloud", choices=["cloud", "local"])
    ap.add_argument("--provider", default="groq")
    ap.add_argument("-k", "--top-k", type=int, default=5)
    args = ap.parse_args()

    final = run(args.question, args.corpus, mode=args.mode,
                provider=args.provider, top_k=args.top_k)

    print(f"\n=== Answer (verified={final.get('verified')}, "
          f"faithfulness={final.get('overall_faithfulness')}) ===\n{final.get('answer', '')}\n")
    claims = final.get("claims", [])
    if claims:
        print("=== Per-claim faithfulness ===")
        for c in claims:
            score = c.get("faithfulness_score")
            tag = "uncited" if not c.get("cited") else (
                "PASS" if c.get("verdict") else "FAIL")
            score_str = "  -  " if score is None else f"{score:.3f}"
            print(f"[{tag:7}] {score_str}  {c.get('claim_text', '')[:90]}")


if __name__ == "__main__":
    main()

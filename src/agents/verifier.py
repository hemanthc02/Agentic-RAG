"""Verifier agent — NLI-based citation faithfulness checker (the novelty).

Each sentence in the synthesized answer is checked against the chunks it cites.
The NLI model (cross-encoder/nli-deberta-v3-base) scores the entailment
probability. Sentences below the threshold are flagged for revision.

Fallback: if the NLI model is not available (first import, OOM, etc.) the
verifier uses the configured LLM to estimate faithfulness via a prompt.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import config
from src.agents.state import AgentState

logger = logging.getLogger(__name__)

_nli_pipeline: Any = None
_nli_load_attempted = False


def _get_nli():
    global _nli_pipeline, _nli_load_attempted
    if _nli_load_attempted:
        return _nli_pipeline
    _nli_load_attempted = True
    try:
        from transformers import pipeline as hf_pipeline
        _nli_pipeline = hf_pipeline(
            "text-classification",
            model=config.NLI_MODEL,
            device=-1,   # CPU
            top_k=None,
        )
        logger.info("NLI model loaded: %s", config.NLI_MODEL)
    except Exception as exc:
        logger.warning("NLI model unavailable (%s) — using LLM fallback", exc)
        _nli_pipeline = None
    return _nli_pipeline


def _premise_windows(premise: str, size: int = 4, stride: int = 2,
                     max_windows: int = 12) -> list[str]:
    """Split evidence text into overlapping sentence windows for NLI scoring.

    MNLI-trained cross-encoders are calibrated on short (1–4 sentence)
    premises. Feeding a whole ~2,000-char chunk yields "neutral" even when the
    supporting sentences are present, collapsing entailment scores for
    genuinely faithful claims. Scoring the claim against each window and taking
    the max asks the right question: does ANY passage in the cited chunk
    entail the claim?

    PDF chunk text carries hard line breaks and hyphenated line-wraps
    ("re-\\ntrieval") that corrupt tokenization, so the text is normalized
    before splitting.
    """
    clean = re.sub(r"-\s*\n\s*", "", premise)
    clean = re.sub(r"\s+", " ", clean).strip()
    sents = _split_sentences(clean)
    if len(sents) <= size:
        return [clean]
    windows = []
    for i in range(0, len(sents), stride):
        w = " ".join(sents[i:i + size]).strip()
        if w:
            windows.append(w)
        if len(windows) >= max_windows:
            break
    return windows or [clean]


def _nli_score(premise: str, hypothesis: str) -> float:
    """Return entailment probability [0,1] for ``hypothesis`` given ``premise``.

    ``premise`` is the cited evidence (chunk text); ``hypothesis`` is the answer
    claim. A cross-encoder NLI model expects these as a **text pair**. The
    chunk is split into overlapping sentence windows (see
    :func:`_premise_windows`) and the claim's score is the maximum entailment
    across windows — one batched pipeline call.
    """
    nli = _get_nli()
    if nli is None:
        return _llm_faithfulness_score(premise, hypothesis)
    try:
        windows = _premise_windows(premise)
        results = nli(
            [{"text": w, "text_pair": hypothesis} for w in windows],
            truncation=True,
            max_length=512,
        )
        # With top_k=None each item is a list of {label, score} dicts; a single
        # input may come back unbatched. Normalize to a list of lists.
        if results and isinstance(results[0], dict):
            results = [results]
        best = 0.0
        for scored in results:
            for r in scored:
                if str(r["label"]).upper().startswith("ENTAIL"):
                    best = max(best, float(r["score"]))
                    break
        return best
    except Exception as exc:
        logger.warning("NLI inference failed: %s", exc)
        return _llm_faithfulness_score(premise, hypothesis)


def _llm_faithfulness_score(premise: str, hypothesis: str) -> float:
    """LLM fallback: ask the model to rate support from 0.0–1.0."""
    try:
        from src.llm_backend import get_backend
        llm = get_backend()
        prompt = (
            f"Rate how well this EVIDENCE supports the CLAIM on a scale 0.0 to 1.0.\n\n"
            f"EVIDENCE: {premise[:800]}\n\nCLAIM: {hypothesis[:300]}\n\n"
            "Return only a decimal number between 0.0 and 1.0."
        )
        raw = llm.generate(prompt, temperature=0.0, max_tokens=8).strip()
        match = re.search(r"[01]?\.\d+|\d", raw)
        return min(1.0, max(0.0, float(match.group()))) if match else 0.5
    except Exception:
        return 0.5


def _extract_citation_refs(text: str) -> list[int]:
    """Extract [1], [2,3], [1][3] style citation indices from a sentence."""
    return [int(n) for n in re.findall(r'\[(\d+)\]', text)]


def _split_sentences(text: str) -> list[str]:
    sents = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sents if s.strip()]


def verify_answer(answer: str, chunks: list[dict]) -> dict:
    """Score an answer's per-claim citation faithfulness against its chunks.

    This is the project's core metric, factored out of :func:`verifier_node` so
    that BOTH the agentic pipeline and the evaluation harness (``src.evaluation``)
    score the baseline and multi-agent answers with the *same* NLI measure.

    Returns a dict with:
        claims               — per-sentence records (see below)
        overall_faithfulness — mean NLI entailment over CITED claims (0.0 if none)
        cited_claims         — number of sentences carrying ≥1 valid citation
        uncited_claims       — number of sentences with no citation
        failed_claims        — cited claims below the faithfulness threshold
        all_cited_pass       — True iff there is ≥1 cited claim and all passed
    """
    sentences = _split_sentences(answer)
    claims: list[dict] = []

    for sent in sentences:
        refs = _extract_citation_refs(sent)
        cited_chunks = [chunks[i - 1] for i in refs if 1 <= i <= len(chunks)]

        if not cited_chunks:
            # No citation → nothing to NLI-verify against. Recorded with NO score
            # (excluded from the faithfulness mean) and verdict ``None`` (not
            # counted as pass/fail). Previously these were given 0.6 + a "mild
            # pass", which inflated the headline metric and let a citation-free
            # answer report ~0.6 faithfulness — gaming the very number this agent
            # exists to protect.
            claims.append({
                "claim_text": sent,
                "cited_chunk_ids": [],
                "cited_chunks": [],
                "faithfulness_score": None,
                "cited": False,
                "verdict": None,
            })
        else:
            # Mean NLI entailment across the cited chunks (§9).
            scores = [_nli_score(c["text"], sent) for c in cited_chunks]
            avg_score = sum(scores) / len(scores)
            claims.append({
                "claim_text": sent,
                "cited_chunk_ids": [c["chunk_id"] for c in cited_chunks],
                "cited_chunks": cited_chunks,
                "faithfulness_score": round(avg_score, 3),
                "cited": True,
                "verdict": avg_score >= config.CITATION_FAITHFULNESS_THRESHOLD,
            })

    cited_claims = [c for c in claims if c["cited"]]
    # Faithfulness = mean NLI entailment over CITED claims only. An answer with
    # zero citations scores 0.0 (not 0.6) and cannot be considered verified.
    overall = (
        round(sum(c["faithfulness_score"] for c in cited_claims) / len(cited_claims), 3)
        if cited_claims
        else 0.0
    )
    return {
        "claims": claims,
        "overall_faithfulness": overall,
        "cited_claims": len(cited_claims),
        "uncited_claims": len(claims) - len(cited_claims),
        "failed_claims": sum(1 for c in cited_claims if not c["verdict"]),
        "all_cited_pass": bool(cited_claims) and all(c["verdict"] for c in cited_claims),
    }


def verifier_node(state: AgentState) -> dict:
    t0 = time.perf_counter()
    answer = state.get("answer", "")
    chunks = state.get("chunks", [])
    revision = state.get("revision_count", 0)

    if not answer or not chunks:
        elapsed = int((time.perf_counter() - t0) * 1000)
        log = state.get("stage_log", [])
        log.append({"stage": "verifier", "claims": 0, "latency_ms": elapsed})
        return {"claims": [], "overall_faithfulness": 0.0, "verified": True,
                "revision_count": revision, "stage_log": log}

    result = verify_answer(answer, chunks)
    claims = result["claims"]
    overall = result["overall_faithfulness"]
    uncited_count = result["uncited_claims"]
    answer_ok = result["all_cited_pass"]
    can_revise = revision < config.MAX_VERIFIER_RETRIES

    elapsed = int((time.perf_counter() - t0) * 1000)
    log = state.get("stage_log", [])
    log.append({
        "stage": "verifier",
        "claims": len(claims),
        "cited_claims": result["cited_claims"],
        "uncited_claims": uncited_count,
        "failed": result["failed_claims"],
        "overall_faithfulness": overall,
        "will_revise": not answer_ok and can_revise,
        "latency_ms": elapsed,
    })

    return {
        # ``verified`` reflects the TRUE verification outcome. We do NOT flip it
        # to True just because the retry budget ran out — exhausting retries on
        # an unfaithful answer means it stays unverified, and the consumer is
        # told so honestly (the old behaviour silently "passed" such answers).
        "claims": claims,
        "overall_faithfulness": overall,
        "verified": answer_ok,
        "revision_count": revision + (0 if answer_ok or not can_revise else 1),
        "stage_log": log,
    }


def should_revise(state: AgentState) -> str:
    """LangGraph routing: 'revise' → synthesizer, 'done' → END.

    Revise only when the answer failed verification AND the retry budget is not
    yet exhausted. When the budget runs out we stop and return the (still
    ``verified=False``) answer rather than looping forever.
    """
    if state.get("verified", False):
        return "done"
    if state.get("revision_count", 0) >= config.MAX_VERIFIER_RETRIES:
        return "done"
    return "revise"

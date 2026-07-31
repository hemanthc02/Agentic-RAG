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
        # Use all CPU cores for inference (verification is the CPU bottleneck).
        try:
            import os as _os
            import torch as _torch
            _torch.set_num_threads(max(1, (_os.cpu_count() or 2)))
        except Exception:
            pass
        from transformers import pipeline as hf_pipeline
        _nli_pipeline = hf_pipeline(
            "text-classification",
            model=config.NLI_MODEL,
            device=-1,        # CPU
            top_k=None,
            batch_size=16,    # batch window-pairs -> far fewer forward passes
        )
        logger.info("NLI model loaded: %s", config.NLI_MODEL)
    except Exception as exc:
        logger.warning("NLI model unavailable (%s) — using LLM fallback", exc)
        _nli_pipeline = None
    return _nli_pipeline


def _premise_windows(premise: str, size: int = 5, stride: int = 3,
                     max_windows: int = 6) -> list[str]:
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
        windows = _premise_windows(premise, max_windows=config.NLI_MAX_WINDOWS)
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


def verify_answer(answer: str, chunks: list[dict],
                  correct_citations: bool = False) -> dict:
    """Score an answer's per-claim citation faithfulness against its chunks.

    This is the project's core metric, factored out of :func:`verifier_node` so
    that BOTH the agentic pipeline and the evaluation harness (``src.evaluation``)
    score the baseline and multi-agent answers with the *same* NLI measure.

    ``correct_citations`` (pipeline path only — NOT the evaluation metric):
    LLMs frequently state a fact that IS in the retrieved set but attach the
    wrong [n] index. When a cited chunk fails, the claim is re-scored against
    the other retrieved chunks; if one entails it above the threshold, the
    citation is remapped to that chunk (recorded via ``corrected_citation``)
    and the marker is rewritten in the answer text. The claim is still
    NLI-verified against real corpus text — only the pointer is repaired.

    Returns a dict with:
        claims               — per-sentence records (see below)
        answer               — the (possibly citation-corrected) answer text
        overall_faithfulness — mean NLI entailment over CITED claims (0.0 if none)
        cited_claims         — number of sentences carrying ≥1 valid citation
        uncited_claims       — number of sentences with no citation
        failed_claims        — cited claims below the faithfulness threshold
        all_cited_pass       — True iff there is ≥1 cited claim and all passed
    """
    sentences = _split_sentences(answer)
    claims: list[dict] = []
    corrected_answer = answer

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
            # A claim is supported if AT LEAST ONE cited chunk entails it
            # (max, not mean: citing a second, weaker source alongside a
            # perfect one shouldn't fail the claim).
            scores = [_nli_score(c["text"], sent) for c in cited_chunks]
            avg_score = max(scores)
            corrected_to: int | None = None

            if (correct_citations
                    and avg_score < config.CITATION_FAITHFULNESS_THRESHOLD
                    and len(refs) == 1):
                # Citation repair: is the claim entailed by a DIFFERENT
                # retrieved chunk? (single-citation sentences only, so the
                # marker rewrite below is unambiguous)
                # PERF: only try the top few most-relevant alternatives and stop
                # the moment one supports the claim. Without this cap, an answer
                # whose claims all fail would trigger claims x chunks x windows
                # NLI passes on CPU — the cause of multi-minute verification.
                cited_ids = {c["chunk_id"] for c in cited_chunks}
                best_idx, best_score = None, avg_score
                tried = 0
                for idx, c in enumerate(chunks, 1):
                    if c["chunk_id"] in cited_ids:
                        continue
                    s = _nli_score(c["text"], sent)
                    if s > best_score:
                        best_idx, best_score = idx, s
                    if best_score >= config.CITATION_FAITHFULNESS_THRESHOLD:
                        break  # found a supporting source — no need to keep scanning
                    tried += 1
                    if tried >= config.MAX_REPAIR_ALTERNATIVES:
                        break
                if best_idx is not None and best_score >= config.CITATION_FAITHFULNESS_THRESHOLD:
                    corrected_to = best_idx
                    fixed_sent = sent.replace(f"[{refs[0]}]", f"[{best_idx}]")
                    corrected_answer = corrected_answer.replace(sent, fixed_sent, 1)
                    cited_chunks = [chunks[best_idx - 1]]
                    avg_score = best_score

            claims.append({
                "claim_text": sent if corrected_to is None else
                sent.replace(f"[{refs[0]}]", f"[{corrected_to}]"),
                "cited_chunk_ids": [c["chunk_id"] for c in cited_chunks],
                "cited_chunks": cited_chunks,
                "faithfulness_score": round(avg_score, 3),
                "cited": True,
                "verdict": avg_score >= config.CITATION_FAITHFULNESS_THRESHOLD,
                "corrected_citation": corrected_to,
            })

    cited_claims = [c for c in claims if c["cited"]]
    # Faithfulness = mean NLI entailment over CITED claims only. An answer with
    # zero citations scores 0.0 (not 0.6) and cannot be considered verified.
    overall = (
        round(sum(c["faithfulness_score"] for c in cited_claims) / len(cited_claims), 3)
        if cited_claims
        else 0.0
    )
    total_claims = len(claims)
    cited_ratio = (len(cited_claims) / total_claims) if total_claims else 0.0
    # "Verified" requires (a) at least one cited claim, (b) every cited claim
    # passes NLI, AND (c) the answer is not dominated by uncited sentences.
    # (c) closes the gaming hole where an answer of many uncited sentences plus
    # one passing cited sentence would otherwise report verified=True.
    all_cited_pass = (
        bool(cited_claims)
        and all(c["verdict"] for c in cited_claims)
        and cited_ratio >= config.MIN_CITED_RATIO
    )
    return {
        "claims": claims,
        "answer": corrected_answer,
        "overall_faithfulness": overall,
        "cited_claims": len(cited_claims),
        "uncited_claims": total_claims - len(cited_claims),
        "cited_ratio": round(cited_ratio, 3),
        "failed_claims": sum(1 for c in cited_claims if not c["verdict"]),
        "all_cited_pass": all_cited_pass,
        "corrected_citations": sum(1 for c in claims if c.get("corrected_citation")),
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

    result = verify_answer(answer, chunks, correct_citations=True)
    claims = result["claims"]
    overall = result["overall_faithfulness"]
    uncited_count = result["uncited_claims"]
    answer_ok = result["all_cited_pass"]
    # Offline: fewer rewrites (each rewrite is a slow CPU generation).
    max_retries = (config.OFFLINE_MAX_REVISIONS
                   if str(state.get("mode", "")).lower() == "local"
                   else config.MAX_VERIFIER_RETRIES)
    can_revise = revision < max_retries

    elapsed = int((time.perf_counter() - t0) * 1000)
    log = state.get("stage_log", [])
    log.append({
        "stage": "verifier",
        "claims": len(claims),
        "cited_claims": result["cited_claims"],
        "uncited_claims": uncited_count,
        "cited_ratio": result["cited_ratio"],
        "failed": result["failed_claims"],
        "corrected_citations": result["corrected_citations"],
        "overall_faithfulness": overall,
        "will_revise": not answer_ok and can_revise,
        "latency_ms": elapsed,
    })

    return {
        "answer": result["answer"],  # citation markers may have been repaired
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
    max_retries = (config.OFFLINE_MAX_REVISIONS
                   if str(state.get("mode", "")).lower() == "local"
                   else config.MAX_VERIFIER_RETRIES)
    if state.get("revision_count", 0) >= max_retries:
        return "done"
    return "revise"

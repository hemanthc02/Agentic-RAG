"""Evaluation harness — the project's core research deliverable (prompt.md §9).

Runs the 20-question benchmark (``data/eval/eval_set.json``) through a chosen
pipeline and reports:

  * **Citation faithfulness** (the novelty metric) — mean NLI entailment of each
    cited claim against its cited chunks, plus the fraction of cited claims that
    clear ``config.CITATION_FAITHFULNESS_THRESHOLD``. Computed with the *same*
    :func:`src.agents.verifier.verify_answer` the live system uses, so baseline
    and multi-agent numbers are directly comparable.
  * **Latency** per question.
  * **RAGAS** faithfulness / answer-relevancy (optional, ``--ragas``; skipped
    gracefully if ``ragas`` or an LLM judge is unavailable).

The headline experiment (``--compare``) runs the vanilla baseline and the
multi-agent pipeline over the same questions and runs a **paired t-test** on the
per-question faithfulness scores — the evidence for the central claim that a
dedicated NLI verifier improves citation faithfulness.

CLI
---
    python -m src.evaluation --pipeline baseline   --corpus default
    python -m src.evaluation --pipeline multiagent --corpus default
    python -m src.evaluation --compare             --corpus default
    python -m src.evaluation --compare --ragas

Requires a built index at ``data/corpora/<corpus>/`` (see
``python -m src.retrieval --build``) and, for cloud mode, ``GROQ_API_KEY``.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import config

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Eval set loading
# --------------------------------------------------------------------------- #
def load_eval_set(path: Path = config.EVAL_SET_PATH) -> list[dict]:
    """Load the hand-curated Q&A pairs from ``eval_set.json``."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    questions = data.get("questions", [])
    if not questions:
        raise ValueError(f"No questions found in {path}")
    return questions


# --------------------------------------------------------------------------- #
# Pure metric helpers (no I/O, no models — directly unit-testable)
# --------------------------------------------------------------------------- #
def citation_pass_rate(cited_claims: int, failed_claims: int) -> float:
    """Fraction of cited claims that cleared the faithfulness threshold."""
    if cited_claims <= 0:
        return 0.0
    return round((cited_claims - failed_claims) / cited_claims, 3)


def aggregate(records: list[dict]) -> dict:
    """Aggregate per-question records into pipeline-level means."""
    if not records:
        return {"n_questions": 0}

    def _mean(key: str) -> float:
        vals = [r[key] for r in records if r.get(key) is not None]
        return round(statistics.fmean(vals), 3) if vals else 0.0

    return {
        "n_questions": len(records),
        "mean_faithfulness": _mean("overall_faithfulness"),
        "mean_citation_pass_rate": _mean("citation_pass_rate"),
        "mean_latency_ms": round(_mean("latency_ms")),
        "mean_cited_claims": _mean("n_cited"),
        "mean_uncited_claims": _mean("n_uncited"),
        "verified_count": sum(1 for r in records if r.get("verified")),
    }


def paired_ttest(sample_a: list[float], sample_b: list[float]) -> dict:
    """Two-sided paired-samples t-test on ``b - a`` (b = treatment).

    Returns ``t``, degrees of freedom ``df``, ``mean_diff``, ``n``, and a
    ``p_value`` (computed via SciPy when available; ``None`` otherwise, with the
    t-statistic still reported so the result is usable).
    """
    if len(sample_a) != len(sample_b):
        raise ValueError("paired t-test requires equal-length samples")
    n = len(sample_a)
    if n < 2:
        return {"t": None, "df": max(0, n - 1), "mean_diff": 0.0, "p_value": None, "n": n}

    diffs = [b - a for a, b in zip(sample_a, sample_b)]
    mean_diff = statistics.fmean(diffs)
    sd = statistics.stdev(diffs)
    if sd == 0:
        # No variance: identical or constant difference.
        t = math.inf if mean_diff != 0 else 0.0
        return {"t": t, "df": n - 1, "mean_diff": round(mean_diff, 4),
                "p_value": 0.0 if mean_diff != 0 else 1.0, "n": n}

    t = mean_diff / (sd / math.sqrt(n))
    df = n - 1
    p_value: float | None = None
    try:
        from scipy import stats  # optional
        p_value = float(2 * stats.t.sf(abs(t), df))
    except Exception:
        logger.info("SciPy not available — reporting t=%.3f (df=%d) without a p-value", t, df)

    return {"t": round(t, 4), "df": df, "mean_diff": round(mean_diff, 4),
            "p_value": (round(p_value, 6) if p_value is not None else None), "n": n}


# --------------------------------------------------------------------------- #
# Pipeline runners → per-question records
# --------------------------------------------------------------------------- #
def _record_from_verification(
    q: dict, answer: str, verification: dict, latency_ms: int, pipeline: str,
) -> dict:
    return {
        "id": q.get("id", ""),
        "question": q.get("question", ""),
        "pipeline": pipeline,
        "answer": answer,
        "n_claims": len(verification["claims"]),
        "n_cited": verification["cited_claims"],
        "n_uncited": verification["uncited_claims"],
        "failed_claims": verification["failed_claims"],
        "overall_faithfulness": verification["overall_faithfulness"],
        "citation_pass_rate": citation_pass_rate(
            verification["cited_claims"], verification["failed_claims"]
        ),
        "verified": verification["all_cited_pass"],
        "latency_ms": latency_ms,
    }


def run_baseline(questions: list[dict], corpus_id: str, mode: str, provider: str,
                 top_k: int) -> list[dict]:
    """Run the vanilla single-agent baseline and score each answer."""
    from src.agents.verifier import verify_answer
    from src.baseline import BaselineRAG
    from src.llm_backend import get_backend
    from src.retrieval import SentenceTransformerEmbedder, VectorStore

    index_path, chunk_path = config.corpus_paths(corpus_id)
    store = VectorStore.load(SentenceTransformerEmbedder(),
                             index_path=index_path, chunk_path=chunk_path)
    rag = BaselineRAG(store, get_backend(mode=mode, provider=provider))

    records: list[dict] = []
    for q in questions:
        t0 = time.perf_counter()
        result = rag.answer(q["question"], k=top_k)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        # Score with the SAME verifier the multi-agent system uses. Chunks are in
        # retrieval order, matching the [n] markers the baseline prompt assigns.
        chunks = [
            {"chunk_id": c.chunk_id, "source": c.source, "page": c.page, "text": c.text}
            for c in result.sources
        ]
        verification = verify_answer(result.answer, chunks)
        records.append(_record_from_verification(
            q, result.answer, verification, latency_ms, "baseline"))
        logger.info("[baseline] %s faithfulness=%.3f", q.get("id"),
                    verification["overall_faithfulness"])
    return records


def run_multiagent(questions: list[dict], corpus_id: str, mode: str, provider: str,
                   top_k: int) -> list[dict]:
    """Run the full LangGraph multi-agent pipeline and score each answer."""
    from src.agents.graph import run as run_graph

    records: list[dict] = []
    for q in questions:
        final = run_graph(q["question"], corpus_id, mode=mode, provider=provider, top_k=top_k)
        claims = final.get("claims", [])
        cited = [c for c in claims if c.get("cited")]
        failed = sum(1 for c in cited if c.get("verdict") is False)
        verification = {
            "claims": claims,
            "overall_faithfulness": final.get("overall_faithfulness", 0.0),
            "cited_claims": len(cited),
            "uncited_claims": len(claims) - len(cited),
            "failed_claims": failed,
            "all_cited_pass": bool(final.get("verified")),
        }
        records.append(_record_from_verification(
            q, final.get("answer", ""), verification,
            final.get("latency_ms", 0), "multiagent"))
        logger.info("[multiagent] %s faithfulness=%.3f verified=%s", q.get("id"),
                    verification["overall_faithfulness"], final.get("verified"))
    return records


PIPELINES: dict[str, Callable[..., list[dict]]] = {
    "baseline": run_baseline,
    "multiagent": run_multiagent,
}


# --------------------------------------------------------------------------- #
# RAGAS (optional, best-effort)
# --------------------------------------------------------------------------- #
def run_ragas(records: list[dict], questions: list[dict]) -> dict | None:
    """Best-effort RAGAS faithfulness/answer-relevancy. Returns None if skipped.

    RAGAS needs an LLM judge and is version-sensitive; any failure is logged and
    returns ``None`` rather than aborting the run. The custom NLI metric above is
    the primary measure — RAGAS is a corroborating reference-light cross-check.
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, faithfulness
    except Exception as exc:  # pragma: no cover - optional dep
        logger.warning("RAGAS unavailable (%s) — skipping RAGAS metrics", exc)
        return None

    try:
        gt = {q.get("id"): q.get("ground_truth", "") for q in questions}
        ds = Dataset.from_dict({
            "question": [r["question"] for r in records],
            "answer": [r["answer"] for r in records],
            "contexts": [[c.get("text", "") for c in
                          (r.get("_contexts") or [])] or [r["answer"]] for r in records],
            "ground_truth": [gt.get(r["id"], "") for r in records],
        })
        result = evaluate(ds, metrics=[faithfulness, answer_relevancy])
        return {k: round(float(v), 4) for k, v in result.items()}
    except Exception as exc:  # pragma: no cover - optional dep
        logger.warning("RAGAS evaluation failed (%s) — skipping", exc)
        return None


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def _write_csv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["id", "pipeline", "question", "overall_faithfulness", "citation_pass_rate",
              "n_claims", "n_cited", "n_uncited", "failed_claims", "verified", "latency_ms"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    logger.info("Wrote per-question CSV → %s", path)


def _write_json(summary: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    logger.info("Wrote summary JSON → %s", path)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _print_summary(title: str, agg: dict) -> None:
    print(f"\n=== {title} ===")
    print(f"  questions               : {agg.get('n_questions')}")
    print(f"  mean faithfulness       : {agg.get('mean_faithfulness')}")
    print(f"  mean citation pass-rate : {agg.get('mean_citation_pass_rate')}")
    print(f"  verified answers        : {agg.get('verified_count')}/{agg.get('n_questions')}")
    print(f"  mean latency (ms)       : {agg.get('mean_latency_ms')}")


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def evaluate_pipeline(name: str, questions: list[dict], corpus_id: str, mode: str,
                      provider: str, top_k: int) -> tuple[list[dict], dict]:
    runner = PIPELINES[name]
    records = runner(questions, corpus_id, mode, provider, top_k)
    return records, aggregate(records)


def main() -> None:  # pragma: no cover - CLI glue
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="RAG evaluation harness (prompt.md §9)")
    ap.add_argument("--pipeline", choices=list(PIPELINES), help="evaluate a single pipeline")
    ap.add_argument("--compare", action="store_true",
                    help="run baseline AND multiagent, then a paired t-test")
    ap.add_argument("--corpus", default=config.DEFAULT_CORPUS_ID)
    ap.add_argument("--mode", default=config.LLM_MODE, choices=["cloud", "local"])
    ap.add_argument("--provider", default=config.LLM_PROVIDER)
    ap.add_argument("-k", "--top-k", type=int, default=config.TOP_K)
    ap.add_argument("--ragas", action="store_true", help="also compute RAGAS metrics (best-effort)")
    ap.add_argument("--eval-set", type=Path, default=config.EVAL_SET_PATH)
    args = ap.parse_args()

    if not args.pipeline and not args.compare:
        ap.error("specify --pipeline {baseline|multiagent} or --compare")

    questions = load_eval_set(args.eval_set)
    index_path, _ = config.corpus_paths(args.corpus)
    if not index_path.exists():
        ap.error(
            f"No index at {index_path}. Build one first:\n"
            f"  python -m src.retrieval --build --corpus {args.corpus}\n"
            f"(after dropping PDFs into {config.PDF_DIR})"
        )

    stamp = _stamp()
    summary: dict[str, Any] = {
        "timestamp_utc": stamp, "corpus": args.corpus, "mode": args.mode,
        "provider": args.provider, "top_k": args.top_k,
        "faithfulness_threshold": config.CITATION_FAITHFULNESS_THRESHOLD,
        "n_questions": len(questions),
    }

    targets = ["baseline", "multiagent"] if args.compare else [args.pipeline]
    per_pipeline: dict[str, list[dict]] = {}
    for name in targets:
        records, agg = evaluate_pipeline(name, questions, args.corpus, args.mode,
                                         args.provider, args.top_k)
        per_pipeline[name] = records
        summary[name] = agg
        _print_summary(f"{name} ({len(records)} questions)", agg)
        _write_csv(records, config.REPORTS_DIR / f"eval_{name}_{stamp}.csv")
        if args.ragas:
            ragas_scores = run_ragas(records, questions)
            if ragas_scores:
                summary.setdefault("ragas", {})[name] = ragas_scores
                print(f"  RAGAS                   : {ragas_scores}")

    if args.compare:
        base = {r["id"]: r["overall_faithfulness"] for r in per_pipeline["baseline"]}
        multi = {r["id"]: r["overall_faithfulness"] for r in per_pipeline["multiagent"]}
        common = [qid for qid in base if qid in multi]
        ttest = paired_ttest([base[q] for q in common], [multi[q] for q in common])
        summary["paired_ttest_faithfulness"] = ttest
        print("\n=== Paired t-test: faithfulness (multiagent − baseline) ===")
        print(f"  questions paired : {ttest['n']}")
        print(f"  mean improvement : {ttest['mean_diff']:+.4f}")
        print(f"  t({ttest['df']})         : {ttest['t']}")
        print(f"  p-value          : {ttest['p_value']}"
              + ("" if ttest["p_value"] is not None else "  (install scipy for p-value)"))

    _write_json(summary, config.REPORTS_DIR / f"eval_summary_{stamp}.json")
    print(f"\nReports written under {config.REPORTS_DIR}")


if __name__ == "__main__":
    main()

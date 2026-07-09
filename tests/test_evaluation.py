"""Tests for the evaluation harness pure-metric helpers (src.evaluation).

These cover the math behind the headline research result — citation pass-rate,
aggregation, and the paired t-test — without running any pipeline or model.
"""

from __future__ import annotations

import config
from src import evaluation as E


def test_citation_pass_rate():
    assert E.citation_pass_rate(0, 0) == 0.0          # no cited claims
    assert E.citation_pass_rate(4, 0) == 1.0          # all pass
    assert E.citation_pass_rate(4, 1) == 0.75         # one failed
    assert E.citation_pass_rate(2, 2) == 0.0          # all failed


def test_aggregate_means():
    records = [
        {"overall_faithfulness": 0.8, "citation_pass_rate": 1.0, "latency_ms": 100,
         "n_cited": 2, "n_uncited": 0, "verified": True},
        {"overall_faithfulness": 0.4, "citation_pass_rate": 0.5, "latency_ms": 300,
         "n_cited": 2, "n_uncited": 1, "verified": False},
    ]
    agg = E.aggregate(records)
    assert agg["n_questions"] == 2
    assert agg["mean_faithfulness"] == 0.6
    assert agg["mean_latency_ms"] == 200
    assert agg["verified_count"] == 1


def test_aggregate_empty():
    assert E.aggregate([])["n_questions"] == 0


def test_paired_ttest_detects_improvement():
    # Multi-agent strictly better on every paired question → significant.
    baseline = [0.30, 0.40, 0.35, 0.50, 0.45]
    multi = [0.70, 0.75, 0.72, 0.80, 0.78]
    res = E.paired_ttest(baseline, multi)
    assert res["n"] == 5
    assert res["mean_diff"] > 0
    assert res["t"] > 0
    # When SciPy is available a real p-value is reported and should be highly
    # significant; without it the harness still returns the t-statistic.
    try:
        import scipy  # noqa: F401
        assert res["p_value"] is not None and res["p_value"] < 0.05
    except ImportError:
        assert res["p_value"] is None


def test_paired_ttest_no_difference():
    same = [0.5, 0.6, 0.7]
    res = E.paired_ttest(same, list(same))
    assert res["mean_diff"] == 0.0
    assert res["p_value"] == 1.0


def test_paired_ttest_length_mismatch():
    import pytest
    with pytest.raises(ValueError):
        E.paired_ttest([0.1, 0.2], [0.1])


def test_load_eval_set_has_questions():
    questions = E.load_eval_set(config.EVAL_SET_PATH)
    assert len(questions) >= 20
    assert all("question" in q and "id" in q for q in questions)

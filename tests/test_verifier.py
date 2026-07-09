"""Tests for the NLI citation verifier — the project's novelty.

These avoid loading the real DeBERTa model by monkeypatching ``_nli_score`` with
a deterministic stub, so they run fast on CPU with no network and no heavy deps.
They lock in the behaviour the gap-analysis fixes introduced:

  * uncited sentences are NOT scored 0.6 / auto-passed (no metric inflation);
  * a fabricated claim whose evidence does not entail it is REJECTED;
  * the retry budget being exhausted does not flip an unfaithful answer to
    ``verified=True``.
"""

from __future__ import annotations

import config
from src.agents import verifier as V


def _chunk(cid: str, text: str) -> dict:
    return {"chunk_id": cid, "source": "paper.pdf", "page": 1, "text": text}


def test_cited_claim_entailed_passes(monkeypatch):
    monkeypatch.setattr(V, "_nli_score", lambda premise, hyp: 0.95)
    chunks = [_chunk("c1", "Self-RAG uses reflection tokens.")]
    out = V.verify_answer("Self-RAG uses reflection tokens [1].", chunks)
    assert out["cited_claims"] == 1
    assert out["failed_claims"] == 0
    assert out["all_cited_pass"] is True
    assert out["overall_faithfulness"] == 0.95


def test_fabricated_claim_is_rejected(monkeypatch):
    # Evidence does not entail the claim → NLI returns a low score.
    monkeypatch.setattr(V, "_nli_score", lambda premise, hyp: 0.05)
    chunks = [_chunk("c1", "The sky is blue.")]
    out = V.verify_answer("CRAG was invented in 1998 [1].", chunks)
    assert out["cited_claims"] == 1
    assert out["failed_claims"] == 1
    assert out["all_cited_pass"] is False
    assert out["overall_faithfulness"] == 0.05


def test_uncited_sentences_are_not_inflated(monkeypatch):
    # Regression for the 0.6 "mild pass" gaming bug: an answer with no citations
    # must score 0.0 and must NOT be considered verified.
    monkeypatch.setattr(V, "_nli_score", lambda premise, hyp: 0.99)
    chunks = [_chunk("c1", "irrelevant")]
    out = V.verify_answer("This is a confident answer with no citation at all.", chunks)
    assert out["cited_claims"] == 0
    assert out["uncited_claims"] == 1
    assert out["overall_faithfulness"] == 0.0
    assert out["all_cited_pass"] is False
    # The uncited claim carries no score and is not auto-passed.
    assert out["claims"][0]["faithfulness_score"] is None
    assert out["claims"][0]["verdict"] is None


def test_mean_is_over_cited_claims_only(monkeypatch):
    scores = iter([0.8, 0.6])  # two cited claims
    monkeypatch.setattr(V, "_nli_score", lambda premise, hyp: next(scores))
    chunks = [_chunk("c1", "a"), _chunk("c2", "b")]
    answer = "First fact [1]. A transition with no citation. Second fact [2]."
    out = V.verify_answer(answer, chunks)
    assert out["cited_claims"] == 2
    assert out["uncited_claims"] == 1
    # mean over cited only = (0.8 + 0.6)/2 = 0.7, NOT diluted/inflated by the uncited one
    assert out["overall_faithfulness"] == 0.7


def test_should_revise_routing(monkeypatch):
    # Unverified + budget remaining → revise.
    assert V.should_revise({"verified": False, "revision_count": 0}) == "revise"
    # Verified → done.
    assert V.should_revise({"verified": True, "revision_count": 0}) == "done"
    # Unverified but budget exhausted → done (do NOT loop forever).
    assert V.should_revise(
        {"verified": False, "revision_count": config.MAX_VERIFIER_RETRIES}
    ) == "done"


def test_verifier_node_exhausted_budget_stays_unverified(monkeypatch):
    monkeypatch.setattr(V, "_nli_score", lambda premise, hyp: 0.05)  # always fails
    chunks = [_chunk("c1", "unrelated")]
    state = {
        "answer": "Unsupported claim [1].",
        "chunks": chunks,
        "revision_count": config.MAX_VERIFIER_RETRIES,
        "stage_log": [],
    }
    out = V.verifier_node(state)
    # Budget exhausted: we stop, but the answer is honestly reported unverified.
    assert out["verified"] is False
    assert out["overall_faithfulness"] == 0.05
    assert out["revision_count"] == config.MAX_VERIFIER_RETRIES  # not incremented past cap

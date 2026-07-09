"""Happy-path unit tests for the planner, retriever, and synthesizer agents
(prompt.md §5, Week 2 acceptance: "at least one happy-path unit test per agent").

LLM and embedding/index access are monkeypatched, so these run with no network,
no API key, and no FAISS/LangGraph install.
"""

from __future__ import annotations

import types

from src.agents import planner as P
from src.agents import retriever as R
from src.agents import synthesizer as S


class _FakeBackend:
    def __init__(self, reply: str):
        self._reply = reply
        self.last_prompt: str | None = None

    def generate(self, prompt, *, temperature=0.0, max_tokens=1024):
        self.last_prompt = prompt
        return self._reply


# --------------------------------------------------------------------------- #
# Planner
# --------------------------------------------------------------------------- #
def test_planner_decomposes_into_sub_questions(monkeypatch):
    fake = _FakeBackend('{"sub_questions": ["What is CRAG?", "What is Self-RAG?"]}')
    monkeypatch.setattr(P, "get_backend", lambda **kw: fake)
    out = P.planner_node({"question": "Compare CRAG and Self-RAG", "mode": "cloud",
                          "provider": "groq", "stage_log": []})
    assert out["sub_questions"] == ["What is CRAG?", "What is Self-RAG?"]


def test_planner_falls_back_to_original_on_llm_error(monkeypatch):
    def _boom(**kw):
        raise RuntimeError("no key")
    monkeypatch.setattr(P, "get_backend", _boom)
    out = P.planner_node({"question": "What is RAG?", "mode": "cloud",
                          "provider": "groq", "stage_log": []})
    assert out["sub_questions"] == ["What is RAG?"]


# --------------------------------------------------------------------------- #
# Retriever
# --------------------------------------------------------------------------- #
class _FakeStore:
    def __init__(self, results):
        self._results = results

    def search(self, query, k):
        return self._results[:k]


def _result(cid, text, score):
    chunk = types.SimpleNamespace(chunk_id=cid, source="p.pdf", page=1, text=text, section="")
    return types.SimpleNamespace(chunk=chunk, score=score)


def test_retriever_returns_empty_when_index_missing(monkeypatch):
    monkeypatch.setattr(R, "_load_store", lambda corpus_id: None)
    out = R.retriever_node({"question": "q", "corpus_id": "x", "top_k": 5,
                            "mode": "cloud", "provider": "groq", "stage_log": []})
    assert out["chunks"] == []
    assert out["retrieval_attempts"] == 1


def test_retriever_merges_and_dedupes(monkeypatch):
    store = _FakeStore([_result("c1", "alpha", 0.9), _result("c2", "beta", 0.8),
                        _result("c1", "alpha", 0.9)])  # c1 duplicated
    monkeypatch.setattr(R, "_load_store", lambda corpus_id: store)
    out = R.retriever_node({"question": "q", "corpus_id": "x", "top_k": 5,
                            "sub_questions": ["q"], "mode": "cloud",
                            "provider": "groq", "stage_log": []})
    ids = [c["chunk_id"] for c in out["chunks"]]
    assert ids == ["c1", "c2"]  # deduped, score-sorted
    assert out["chunks"][0]["score"] == 0.9


# --------------------------------------------------------------------------- #
# Synthesizer
# --------------------------------------------------------------------------- #
def test_synthesizer_no_chunks_returns_honest_message():
    out = S.synthesizer_node({"question": "q", "chunks": [], "mode": "cloud",
                              "provider": "groq", "stage_log": []})
    assert "could not find" in out["answer"].lower()


def test_synthesizer_wraps_sources_and_returns_answer(monkeypatch):
    fake = _FakeBackend("Self-RAG uses reflection tokens [1].")
    monkeypatch.setattr(S, "get_backend", lambda **kw: fake)
    chunks = [{"chunk_id": "c1", "source": "selfrag.pdf", "page": 3,
               "text": "Reflection tokens control retrieval."}]
    out = S.synthesizer_node({"question": "What is Self-RAG?", "chunks": chunks,
                              "mode": "cloud", "provider": "groq", "stage_log": []})
    assert out["answer"] == "Self-RAG uses reflection tokens [1]."
    # Untrusted source text is wrapped in delimiters (prompt-injection hardening).
    assert "<sources>" in fake.last_prompt and "</sources>" in fake.last_prompt


def test_synthesizer_revision_hint_lists_failed_claims(monkeypatch):
    fake = _FakeBackend("Revised answer [1].")
    monkeypatch.setattr(S, "get_backend", lambda **kw: fake)
    chunks = [{"chunk_id": "c1", "source": "p.pdf", "page": 1, "text": "evidence"}]
    state = {
        "question": "q", "chunks": chunks, "mode": "cloud", "provider": "groq",
        "revision_count": 1, "stage_log": [],
        "claims": [{"claim_text": "Bogus claim [1].", "cited": True, "verdict": False}],
    }
    S.synthesizer_node(state)
    assert "Bogus claim" in fake.last_prompt

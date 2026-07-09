"""Unit tests for src/baseline.py using fakes (no model, no LLM, no network)."""

from __future__ import annotations

from src.baseline import BaselineRAG
from src.ingestion import Chunk
from src.llm_backend import LLMBackend
from src.prompts.baseline import build_baseline_prompt
from src.retrieval import RetrievalResult


class FakeStore:
    def __init__(self, chunks):
        self._chunks = chunks

    def search(self, query, k=5):
        return [RetrievalResult(chunk=c, score=1.0 - i * 0.1)
                for i, c in enumerate(self._chunks[:k])]


class FakeBackend(LLMBackend):
    name = "fake"

    def __init__(self):
        self.last_prompt = None

    def generate(self, prompt, *, temperature=0.0, max_tokens=1024):
        self.last_prompt = prompt
        return "Self-RAG uses reflection tokens [1] and adaptive retrieval [2]."


def _chunks():
    return [
        Chunk(text="Self-RAG reflection tokens.", source="a.pdf", page=1, chunk_id="a::p1::c0"),
        Chunk(text="Adaptive retrieval on demand.", source="a.pdf", page=2, chunk_id="a::p2::c0"),
    ]


def test_prompt_includes_numbered_context_and_question():
    prompt = build_baseline_prompt("What is Self-RAG?", ["ctx one", "ctx two"])
    assert "[1] ctx one" in prompt and "[2] ctx two" in prompt
    assert "What is Self-RAG?" in prompt


def test_baseline_answer_shape_and_sources():
    backend = FakeBackend()
    rag = BaselineRAG(FakeStore(_chunks()), backend)
    result = rag.answer("What is Self-RAG?", k=2)
    assert result.backend == "fake"
    assert "[1]" in result.answer
    assert len(result.sources) == 2
    # the backend received the retrieved context
    assert "Self-RAG reflection tokens." in backend.last_prompt

"""Vanilla single-agent RAG baseline (Phase 1 / Week 1, task 5).

The comparison baseline the multi-agent system must beat: embed the question →
retrieve top-k chunks → stuff into one prompt → LLM → return answer + sources.
All LLM access goes through ``llm_backend`` (§8).

CLI:
    python -m src.baseline "What is Self-RAG?"
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

import config
from src.ingestion import Chunk
from src.llm_backend import LLMBackend, get_backend
from src.prompts.baseline import build_baseline_prompt
from src.retrieval import RetrievalResult, SentenceTransformerEmbedder, VectorStore

logger = logging.getLogger(__name__)


class BaselineAnswer(BaseModel):
    question: str
    answer: str
    sources: list[Chunk]
    backend: str


class BaselineRAG:
    """Single-shot retrieve-then-generate pipeline."""

    def __init__(self, store: VectorStore, backend: LLMBackend) -> None:
        self._store = store
        self._backend = backend

    def answer(self, question: str, k: int = config.TOP_K) -> BaselineAnswer:
        results: list[RetrievalResult] = self._store.search(question, k=k)
        contexts = [r.chunk.text for r in results]
        prompt = build_baseline_prompt(question, contexts)
        text = self._backend.generate(prompt)
        return BaselineAnswer(
            question=question,
            answer=text,
            sources=[r.chunk for r in results],
            backend=self._backend.name,
        )


def _load_default() -> BaselineRAG:  # pragma: no cover - integration glue
    store = VectorStore.load(SentenceTransformerEmbedder())
    return BaselineRAG(store, get_backend())


def main() -> None:  # pragma: no cover - CLI glue
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Vanilla baseline RAG")
    ap.add_argument("question", help="question to answer")
    ap.add_argument("-k", type=int, default=config.TOP_K)
    args = ap.parse_args()

    pipeline = _load_default()
    result = pipeline.answer(args.question, k=args.k)
    print(f"\n=== Answer ({result.backend}) ===\n{result.answer}\n")
    print("=== Sources ===")
    seen: set[str] = set()
    for i, c in enumerate(result.sources, start=1):
        tag = f"{c.source} p{c.page}"
        if tag not in seen:
            print(f"[{i}] {tag}")
            seen.add(tag)


if __name__ == "__main__":
    main()

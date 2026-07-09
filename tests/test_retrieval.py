"""Unit tests for src/retrieval.py using a fake embedder (no model download)."""

from __future__ import annotations

import numpy as np
import pytest

from src.ingestion import Chunk
from src.retrieval import RetrievalResult, VectorStore

faiss = pytest.importorskip("faiss")  # skip if faiss-cpu not installed


class FakeEmbedder:
    """Deterministic embedder: maps known texts to fixed unit vectors."""

    dim = 3

    _MAP = {
        "self-rag reflection tokens": [1.0, 0.0, 0.0],
        "corrective rag retrieval evaluator": [0.0, 1.0, 0.0],
        "faiss vector index": [0.0, 0.0, 1.0],
    }

    def encode(self, texts: list[str]) -> np.ndarray:
        out = []
        for t in texts:
            out.append(self._MAP.get(t.lower(), [0.33, 0.33, 0.33]))
        return np.array(out, dtype="float32")


def _chunks() -> list[Chunk]:
    return [
        Chunk(text="self-rag reflection tokens", source="a.pdf", page=1, chunk_id="a::p1::c0"),
        Chunk(text="corrective rag retrieval evaluator", source="b.pdf", page=2, chunk_id="b::p2::c0"),
        Chunk(text="faiss vector index", source="c.pdf", page=1, chunk_id="c::p1::c0"),
    ]


def test_build_and_search_returns_nearest():
    store = VectorStore(FakeEmbedder())
    store.build(_chunks())
    results = store.search("self-rag reflection tokens", k=1)
    assert len(results) == 1
    assert isinstance(results[0], RetrievalResult)
    assert results[0].chunk.source == "a.pdf"
    assert results[0].score == pytest.approx(1.0, abs=1e-3)


def test_search_orders_by_similarity():
    store = VectorStore(FakeEmbedder())
    store.build(_chunks())
    results = store.search("corrective rag retrieval evaluator", k=3)
    assert results[0].chunk.source == "b.pdf"  # best match first
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_build_empty_raises():
    with pytest.raises(ValueError):
        VectorStore(FakeEmbedder()).build([])


def test_save_and_load_roundtrip(tmp_path):
    idx = tmp_path / "f.index"
    chunks = tmp_path / "chunks.pkl"
    store = VectorStore(FakeEmbedder())
    store.build(_chunks())
    store.save(idx, chunks)
    loaded = VectorStore.load(FakeEmbedder(), idx, chunks)
    res = loaded.search("faiss vector index", k=1)
    assert res[0].chunk.source == "c.pdf"

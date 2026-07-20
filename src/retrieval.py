"""Embeddings + FAISS vector store (Phase 1 / Week 1, task 4).

Embeds chunks with a CPU-friendly sentence-transformer (MiniLM by default),
builds and persists a FAISS index, and exposes ``search(query, k)``. The
embedder is injectable so the store can be unit-tested without a model.

CLI:
    python -m src.retrieval --build      # ingest corpus + build/persist index
    python -m src.retrieval "query"      # search the persisted index
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Protocol

import numpy as np
from pydantic import BaseModel

import config
from src.ingestion import Chunk, ingest_corpus

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    """Minimal embedding interface (injectable for tests)."""

    dim: int

    def encode(self, texts: list[str]) -> np.ndarray:
        """Return an (n, dim) float32 array of embeddings."""
        ...


class SentenceTransformerEmbedder:
    """Default CPU embedder backed by sentence-transformers (lazy import)."""

    def __init__(self, model_name: str = config.EMBEDDING_MODEL) -> None:
        from sentence_transformers import SentenceTransformer  # lazy

        self._model = SentenceTransformer(model_name, device="cpu")
        get_dim = getattr(self._model, "get_embedding_dimension", None) \
            or self._model.get_sentence_embedding_dimension
        self.dim = get_dim()

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False
        )
        return vecs.astype("float32")


# Process-wide singletons. The embedding model costs seconds to load on CPU,
# so every agent/router must share ONE instance instead of constructing its own.
import threading

_shared_embedder: SentenceTransformerEmbedder | None = None
_embedder_lock = threading.Lock()
# Loaded vector stores keyed by corpus id; the index-file mtime invalidates the
# entry when an upload rebuilds the index on disk.
_store_cache: dict[str, tuple[float, "VectorStore"]] = {}


def get_shared_embedder() -> SentenceTransformerEmbedder:
    """Return the process-wide embedder, loading the model on first use.

    Lock prevents the startup pre-warm thread and a concurrent request from
    each loading their own copy of the model on this low-RAM machine.
    """
    global _shared_embedder
    with _embedder_lock:
        if _shared_embedder is None:
            _shared_embedder = SentenceTransformerEmbedder()
        return _shared_embedder


def drop_cached_store(corpus_id: str) -> None:
    """Evict a corpus's cached vector store (after delete/rebuild) so the next
    load reads fresh from disk instead of serving a stale in-memory copy."""
    _store_cache.pop(corpus_id, None)


def load_vector_store(corpus_id: str = config.DEFAULT_CORPUS_ID) -> "VectorStore | None":
    """Load a corpus's vector store, reusing a cached copy while the index
    file on disk is unchanged. Returns None if the corpus has no index yet."""
    idx_path, chunk_path = config.corpus_paths(corpus_id)
    if not idx_path.exists():
        return None
    mtime = idx_path.stat().st_mtime
    cached = _store_cache.get(corpus_id)
    if cached and cached[0] == mtime:
        return cached[1]
    store = VectorStore.load(get_shared_embedder(),
                             index_path=idx_path, chunk_path=chunk_path)
    _store_cache[corpus_id] = (mtime, store)
    return store


class RetrievalResult(BaseModel):
    chunk: Chunk
    score: float


def _normalize(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return x / norms


class VectorStore:
    """FAISS-backed store over ``Chunk`` objects (cosine via inner product).

    Flat index up to ``config.FAISS_FLAT_MAX_CHUNKS`` (exact); IVF above that.
    """

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._index = None  # faiss.Index
        self._chunks: list[Chunk] = []

    def build(self, chunks: list[Chunk]) -> None:
        import faiss  # lazy

        if not chunks:
            raise ValueError("cannot build an index from zero chunks")
        self._chunks = list(chunks)
        vecs = _normalize(self._embedder.encode([c.text for c in self._chunks]))
        dim = vecs.shape[1]
        if len(self._chunks) <= config.FAISS_FLAT_MAX_CHUNKS:
            index = faiss.IndexFlatIP(dim)
        else:
            nlist = max(1, int(np.sqrt(len(self._chunks))))
            quantizer = faiss.IndexFlatIP(dim)
            index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)
            index.train(vecs)
        index.add(vecs)
        self._index = index
        logger.info("Built FAISS index: %d vectors, dim=%d", len(self._chunks), dim)

    def save(self, index_path: Path = config.FAISS_INDEX_PATH,
             chunk_path: Path = config.CHUNK_STORE_PATH) -> None:
        import faiss

        if self._index is None:
            raise RuntimeError("nothing to save; build the index first")
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(index_path))
        with open(chunk_path, "wb") as fh:
            pickle.dump([c.model_dump() for c in self._chunks], fh)
        logger.info("Saved index and %d chunks", len(self._chunks))

    @classmethod
    def load(cls, embedder: Embedder, index_path: Path = config.FAISS_INDEX_PATH,
             chunk_path: Path = config.CHUNK_STORE_PATH) -> "VectorStore":
        import faiss

        store = cls(embedder)
        store._index = faiss.read_index(str(index_path))
        with open(chunk_path, "rb") as fh:
            store._chunks = [Chunk(**d) for d in pickle.load(fh)]
        logger.info("Loaded index with %d chunks", len(store._chunks))
        return store

    @property
    def chunks(self) -> list[Chunk]:
        """Read-only view of the indexed chunks (used for incremental rebuilds)."""
        return list(self._chunks)

    def search(self, query: str, k: int = config.TOP_K) -> list[RetrievalResult]:
        if self._index is None:
            raise RuntimeError("index not built/loaded")
        qv = _normalize(self._embedder.encode([query]))
        scores, idxs = self._index.search(qv, min(k, len(self._chunks)))
        results: list[RetrievalResult] = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            results.append(RetrievalResult(chunk=self._chunks[idx], score=float(score)))
        return results


def build_and_persist(corpus_id: str = config.DEFAULT_CORPUS_ID) -> VectorStore:  # pragma: no cover - integration glue
    """Ingest ``data/pdfs/`` and persist the index under ``data/corpora/<id>/``.

    Writing to the shared per-corpus path means the index is immediately usable
    by the agentic pipeline (``python -m src.graph "..." --corpus <id>``) and the
    FastAPI app, which read the same location.
    """
    index_path, chunk_path = config.corpus_paths(corpus_id)
    store = VectorStore(SentenceTransformerEmbedder())
    store.build(ingest_corpus())
    store.save(index_path=index_path, chunk_path=chunk_path)
    return store


def main() -> None:  # pragma: no cover - CLI glue
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="ingest corpus and build the index")
    ap.add_argument("--corpus", default=config.DEFAULT_CORPUS_ID,
                    help="corpus id under data/corpora/ (default: %(default)s)")
    ap.add_argument("query", nargs="?", help="query to search the persisted index")
    args = ap.parse_args()
    index_path, chunk_path = config.corpus_paths(args.corpus)
    if args.build:
        build_and_persist(args.corpus)
    if args.query:
        store = VectorStore.load(SentenceTransformerEmbedder(),
                                 index_path=index_path, chunk_path=chunk_path)
        for r in store.search(args.query):
            print(f"[{r.score:.3f}] {r.chunk.source} p{r.chunk.page}: {r.chunk.text[:100]!r}")


if __name__ == "__main__":
    main()

"""Vector-search seam: FAISS on local disk (default) or Azure AI Search.

One tiny module both the FastAPI document routes and the agent retriever call,
so switching the vector store is a single env var (``config.SEARCH_BACKEND``)
with no change to the pipeline. The FAISS branch is the original code path,
unchanged, so local behaviour is identical to before this seam existed.
"""

from __future__ import annotations

import config


def _use_azure() -> bool:
    return config.SEARCH_BACKEND == "azure_search"


# --------------------------------------------------------------------------- #
# Read — return a store exposing .search(query, k) -> list[RetrievalResult]
# --------------------------------------------------------------------------- #

def get_store(corpus_id: str):
    """Return the corpus's search store, or None if it has no indexed content."""
    if _use_azure():
        from app.backend.azure_search import AzureSearchStore, corpus_has_docs
        return AzureSearchStore(corpus_id) if corpus_has_docs(corpus_id) else None
    from src.retrieval import load_vector_store
    return load_vector_store(corpus_id)


# --------------------------------------------------------------------------- #
# Write — add / remove documents
# --------------------------------------------------------------------------- #

def index_add(corpus_id: str, new_chunks: list) -> None:
    """Index newly ingested chunks for a corpus."""
    if _use_azure():
        from app.backend.azure_search import upsert_chunks
        upsert_chunks(corpus_id, new_chunks)
        return

    # FAISS: rebuild the corpus index from existing + new chunks (original logic).
    from src.retrieval import VectorStore, get_shared_embedder

    idx_path, chunk_path = config.corpus_paths(corpus_id)
    embedder = get_shared_embedder()
    existing: list = []
    if idx_path.exists():
        existing = VectorStore.load(embedder, index_path=idx_path, chunk_path=chunk_path).chunks
    store = VectorStore(embedder)
    store.build(existing + list(new_chunks))
    store.save(index_path=idx_path, chunk_path=chunk_path)


def index_remove_document(corpus_id: str, filename: str) -> None:
    """Remove one document's chunks from the corpus index."""
    if _use_azure():
        from app.backend.azure_search import delete_document
        delete_document(corpus_id, filename)
        return

    # FAISS: rebuild from the chunks NOT belonging to ``filename`` (original logic).
    from src.retrieval import VectorStore, drop_cached_store, get_shared_embedder

    idx_path, chunk_path = config.corpus_paths(corpus_id)
    if not idx_path.exists():
        return
    embedder = get_shared_embedder()
    survivors = [
        c for c in VectorStore.load(embedder, index_path=idx_path, chunk_path=chunk_path).chunks
        if c.source != filename
    ]
    if survivors:
        store = VectorStore(embedder)
        store.build(survivors)
        store.save(index_path=idx_path, chunk_path=chunk_path)
    else:
        idx_path.unlink(missing_ok=True)
        chunk_path.unlink(missing_ok=True)
    drop_cached_store(corpus_id)


def index_drop(corpus_id: str) -> None:
    """Delete a corpus's entire index (called on corpus delete)."""
    if _use_azure():
        from app.backend.azure_search import delete_corpus
        delete_corpus(corpus_id)
        return
    import shutil

    idx_dir = config.DATA_DIR / "corpora" / corpus_id
    if idx_dir.exists():
        shutil.rmtree(idx_dir, ignore_errors=True)

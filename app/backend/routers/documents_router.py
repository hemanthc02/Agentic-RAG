"""Document management: corpora, PDF upload, indexing."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel

import config
from app.backend import auth, cache as cache_mod
from app.backend import database as db
from app.backend.security.guardrails import (
    sanitize_chunk_text, sanitize_filename, validate_pdf_magic_bytes,
)

router = APIRouter(prefix="/api", tags=["documents"])

MAX_PDFS_PER_CORPUS = 20
MAX_FILE_MB = 50


# ---------------------------------------------------------------------------
# Corpora
# ---------------------------------------------------------------------------

class CorpusCreate(BaseModel):
    name: str


@router.get("/corpora")
def list_corpora(user: Annotated[dict, Depends(auth.get_current_user)]):
    return db.list_corpora(user["id"])


@router.post("/corpora", status_code=201)
def create_corpus(body: CorpusCreate,
                  user: Annotated[dict, Depends(auth.get_current_user)]):
    return db.create_corpus(user["id"], body.name.strip())


@router.delete("/corpora/{corpus_id}", status_code=204)
def delete_corpus(corpus_id: str,
                  user: Annotated[dict, Depends(auth.get_current_user)]):
    corpus = db.get_corpus(corpus_id, user["id"])
    if not corpus:
        raise HTTPException(404, "Corpus not found")
    # Remove the FAISS index directory AND the uploaded PDFs on disk.
    idx_dir = config.DATA_DIR / "corpora" / corpus_id
    if idx_dir.exists():
        shutil.rmtree(idx_dir, ignore_errors=True)
    pdf_dir = config.PDF_DIR / corpus_id
    if pdf_dir.exists():
        shutil.rmtree(pdf_dir, ignore_errors=True)
    # Cascade the DB rows, then purge the non-cascading corpus-keyed tables
    # (KG, query history, viva sessions) so nothing is left behind.
    db.delete_corpus(corpus_id, user["id"])
    db.purge_corpus_data(corpus_id)
    from src.retrieval import drop_cached_store
    drop_cached_store(corpus_id)
    cache_mod.invalidate_corpus(corpus_id)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@router.get("/corpora/{corpus_id}/documents")
def list_documents(corpus_id: str,
                   user: Annotated[dict, Depends(auth.get_current_user)]):
    if not db.get_corpus(corpus_id, user["id"]):
        raise HTTPException(404, "Corpus not found")
    return db.list_documents(corpus_id)


@router.get("/corpora/{corpus_id}/file")
def get_pdf_file(
    corpus_id: str,
    user: Annotated[dict, Depends(auth.get_current_user)],
    name: str = Query(..., description="The stored PDF filename (chunk source)"),
):
    """Serve a corpus PDF so the frontend can display it in an in-app viewer.

    Access is gated on corpus ownership; ``name`` is reduced to a bare filename
    to prevent any path traversal outside the corpus's PDF directory.
    """
    if not db.get_corpus(corpus_id, user["id"]):
        raise HTTPException(404, "Corpus not found")
    safe = Path(name).name  # strip any path components
    path = config.PDF_DIR / corpus_id / safe
    if not path.is_file():
        raise HTTPException(404, "PDF not found")
    return FileResponse(str(path), media_type="application/pdf", filename=safe)


@router.post("/corpora/{corpus_id}/upload", status_code=201)
async def upload_pdfs(
    corpus_id: str,
    user: Annotated[dict, Depends(auth.get_current_user)],
    files: list[UploadFile] = File(...),
):
    corpus = db.get_corpus(corpus_id, user["id"])
    if not corpus:
        raise HTTPException(404, "Corpus not found")

    existing_count = len(db.list_documents(corpus_id))
    if existing_count + len(files) > MAX_PDFS_PER_CORPUS:
        raise HTTPException(
            400,
            f"Corpus already has {existing_count} PDFs. "
            f"Max {MAX_PDFS_PER_CORPUS} per corpus (GPU tier allows more).",
        )

    save_dir = config.PDF_DIR / corpus_id
    save_dir.mkdir(parents=True, exist_ok=True)
    idx_dir = config.DATA_DIR / "corpora" / corpus_id
    idx_dir.mkdir(parents=True, exist_ok=True)

    results = []
    all_new_chunks = []

    for upload in files:
        if not upload.filename.lower().endswith(".pdf"):
            continue
        file_size = 0
        safe_name = f"{uuid.uuid4().hex}_{sanitize_filename(upload.filename)}"
        dest = save_dir / safe_name

        with dest.open("wb") as f:
            while chunk := await upload.read(1024 * 1024):
                file_size += len(chunk)
                if file_size > MAX_FILE_MB * 1024 * 1024:
                    dest.unlink(missing_ok=True)
                    raise HTTPException(400, f"{upload.filename} exceeds {MAX_FILE_MB} MB limit")
                f.write(chunk)

        # Validate it's actually a PDF (magic bytes)
        first_bytes = dest.read_bytes()[:4]
        if not validate_pdf_magic_bytes(first_bytes):
            dest.unlink(missing_ok=True)
            results.append({"filename": upload.filename, "error": "Not a valid PDF file"})
            continue

        # Index the PDF. ingest_pdf is CPU-heavy (PyMuPDF parse) — run it in a
        # threadpool so it doesn't block the async event loop / other requests.
        try:
            from src.ingestion import ingest_pdf
            chunks = await run_in_threadpool(ingest_pdf, dest)
        except Exception as exc:
            dest.unlink(missing_ok=True)
            results.append({"filename": upload.filename, "error": str(exc)})
            continue

        # Neutralize prompt-injection strings embedded in the PDF text before it
        # is ever indexed or fed to any LLM (defense wired at the ingest chokepoint).
        for c in chunks:
            c.text = sanitize_chunk_text(c.text)

        all_new_chunks.extend(chunks)
        doc = db.create_document(
            corpus_id=corpus_id, user_id=user["id"],
            filename=safe_name, original_name=upload.filename,
            page_count=max((c.page for c in chunks), default=0),
            chunk_count=len(chunks), file_size=file_size,
        )
        db.update_corpus_counts(corpus_id, doc_delta=1, chunk_delta=len(chunks))
        results.append({**doc, "original_name": upload.filename, "chunk_count": len(chunks)})

    # Rebuild the corpus-level FAISS index incrementally (embedding is CPU-heavy
    # — offload so the event loop stays responsive during indexing).
    if all_new_chunks:
        await run_in_threadpool(_rebuild_index, corpus_id, all_new_chunks)
        from src.retrieval import drop_cached_store
        drop_cached_store(corpus_id)
        cache_mod.invalidate_corpus(corpus_id)

    return {"indexed": results, "total_new_chunks": len(all_new_chunks)}


def _rebuild_index(corpus_id: str, new_chunks: list) -> None:
    """Add new chunks to the corpus FAISS index (rebuild from all chunks)."""
    idx_path, chunk_path = config.corpus_paths(corpus_id)

    from src.retrieval import VectorStore, get_shared_embedder

    embedder = get_shared_embedder()

    # Load existing chunks if the index already exists, then rebuild from all.
    existing: list = []
    if idx_path.exists():
        existing = VectorStore.load(
            embedder, index_path=idx_path, chunk_path=chunk_path
        ).chunks

    store = VectorStore(embedder)
    store.build(existing + new_chunks)
    store.save(index_path=idx_path, chunk_path=chunk_path)


@router.delete("/corpora/{corpus_id}/documents/{doc_id}", status_code=204)
def delete_document(corpus_id: str, doc_id: str,
                    user: Annotated[dict, Depends(auth.get_current_user)]):
    doc = db.delete_document(doc_id, user["id"])
    if not doc:
        raise HTTPException(404, "Document not found")
    pdf_path = config.PDF_DIR / corpus_id / doc["filename"]
    if pdf_path.exists():
        pdf_path.unlink()
    # Rebuild the FAISS index WITHOUT this document's chunks. Previously the
    # index was untouched, so a "deleted" document stayed retrievable and
    # citable — deletion was cosmetic. chunk.source == document.filename.
    _remove_document_from_index(corpus_id, doc["filename"])
    db.update_corpus_counts(corpus_id, doc_delta=-1, chunk_delta=-doc.get("chunk_count", 0))
    cache_mod.invalidate_corpus(corpus_id)


def _remove_document_from_index(corpus_id: str, filename: str) -> None:
    """Rebuild the corpus index from the chunks NOT belonging to ``filename``."""
    idx_path, chunk_path = config.corpus_paths(corpus_id)
    if not idx_path.exists():
        return
    from src.retrieval import VectorStore, get_shared_embedder, drop_cached_store

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
        # No chunks left — remove the index files so an empty corpus reads clean.
        idx_path.unlink(missing_ok=True)
        chunk_path.unlink(missing_ok=True)
    drop_cached_store(corpus_id)

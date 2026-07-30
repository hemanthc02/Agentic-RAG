"""Document management: corpora, PDF upload, indexing."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

import config
from app.backend import auth, cache as cache_mod
from app.backend import database as db
from app.backend import storage
from app.backend.security.guardrails import (
    sanitize_chunk_text, sanitize_filename, validate_pdf_magic_bytes,
)
from src import search_backend

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
    # Remove the vector index AND the uploaded PDFs (local disk or Azure).
    search_backend.index_drop(corpus_id)
    storage.delete_corpus_pdfs(corpus_id)
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
    if config.STORAGE_BACKEND == "azure_blob":
        data = storage.read_pdf(corpus_id, safe)
        if data is None:
            raise HTTPException(404, "PDF not found")
        return Response(content=data, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{safe}"'})
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
        # Persist the PDF to its permanent home. Local mode already wrote it to
        # PDF_DIR (that IS the store); Azure mode uploads to Blob and drops the
        # temp working file.
        if config.STORAGE_BACKEND == "azure_blob":
            storage.save_pdf(corpus_id, safe_name, dest.read_bytes())
            dest.unlink(missing_ok=True)
        results.append({**doc, "original_name": upload.filename, "chunk_count": len(chunks)})

    # Index the new chunks (FAISS rebuild on disk, or upsert to Azure AI Search).
    # Embedding is CPU-heavy — offload so the event loop stays responsive.
    if all_new_chunks:
        await run_in_threadpool(search_backend.index_add, corpus_id, all_new_chunks)
        from src.retrieval import drop_cached_store
        drop_cached_store(corpus_id)
        cache_mod.invalidate_corpus(corpus_id)

    return {"indexed": results, "total_new_chunks": len(all_new_chunks)}


@router.delete("/corpora/{corpus_id}/documents/{doc_id}", status_code=204)
def delete_document(corpus_id: str, doc_id: str,
                    user: Annotated[dict, Depends(auth.get_current_user)]):
    doc = db.delete_document(doc_id, user["id"])
    if not doc:
        raise HTTPException(404, "Document not found")
    storage.delete_pdf(corpus_id, doc["filename"])
    # Remove this document's chunks from the index so a "deleted" document is no
    # longer retrievable or citable. chunk.source == document.filename.
    search_backend.index_remove_document(corpus_id, doc["filename"])
    db.update_corpus_counts(corpus_id, doc_delta=-1, chunk_delta=-doc.get("chunk_count", 0))
    cache_mod.invalidate_corpus(corpus_id)

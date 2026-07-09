"""Download a research paper PDF and auto-ingest it into a corpus."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

import httpx

import config

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "ResearchRAG/1.0 (academic research tool)"}


async def download_and_ingest(pdf_url: str, corpus_id: str, title: str = "") -> dict:
    """Download PDF from url, save to data/pdfs/<corpus_id>/, then ingest.

    Returns dict with: success, filename, page_count, chunk_count, error
    """
    if not pdf_url.startswith("https://"):
        return {"success": False, "error": "Only HTTPS PDF URLs are allowed"}

    safe_name = _safe_filename(title or pdf_url.split("/")[-1])
    if not safe_name.endswith(".pdf"):
        safe_name += ".pdf"

    pdf_dir = config.PDF_DIR / corpus_id
    pdf_dir.mkdir(parents=True, exist_ok=True)
    dest = pdf_dir / safe_name

    if dest.exists():
        dest = pdf_dir / f"{dest.stem}_{uuid.uuid4().hex[:6]}.pdf"

    # Download
    try:
        async with httpx.AsyncClient(timeout=30.0, headers=_HEADERS,
                                     follow_redirects=True) as client:
            r = await client.get(pdf_url)
            r.raise_for_status()
            content = r.content
            if not content.startswith(b"%PDF"):
                return {"success": False, "error": "Downloaded file is not a valid PDF"}
            if len(content) > 50 * 1024 * 1024:
                return {"success": False, "error": "PDF exceeds 50 MB limit"}
            dest.write_bytes(content)
    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    # Ingest using the same pipeline as documents_router
    try:
        from src.ingestion import ingest_pdf
        chunks = ingest_pdf(dest)

        if not chunks:
            dest.unlink(missing_ok=True)
            return {"success": False, "error": "PDF downloaded but could not be parsed"}

        from src.retrieval import SentenceTransformerEmbedder, VectorStore
        idx_path, chunk_path = config.corpus_paths(corpus_id)
        embedder = SentenceTransformerEmbedder()

        existing: list = []
        if idx_path.exists():
            existing = VectorStore.load(
                embedder, index_path=idx_path, chunk_path=chunk_path
            ).chunks

        store = VectorStore(embedder)
        store.build(existing + chunks)
        store.save(index_path=idx_path, chunk_path=chunk_path)

        return {
            "success": True,
            "filename": dest.name,
            "page_count": max((c.page for c in chunks), default=0),
            "chunk_count": len(chunks),
        }
    except Exception as e:
        logger.error("Ingestion failed: %s", e)
        return {"success": False, "error": f"Download OK but ingestion failed: {e}",
                "filename": dest.name}


def _safe_filename(name: str) -> str:
    name = re.sub(r"[^\w\s\-.]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:120] or "paper"

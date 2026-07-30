"""PDF storage abstraction — local disk (default) or Azure Blob Storage.

Selected by ``config.STORAGE_BACKEND`` ("local" | "azure_blob"). The Azure SDK
is imported lazily so the app runs with no Azure packages installed as long as
the backend stays "local".

Blob layout mirrors the on-disk layout: one blob per PDF, named
``<corpus_id>/<stored_filename>`` inside a single container.
"""

from __future__ import annotations

import shutil

import config


def _use_azure() -> bool:
    return config.STORAGE_BACKEND == "azure_blob"


# --------------------------------------------------------------------------- #
# Azure Blob helpers (lazy)
# --------------------------------------------------------------------------- #
_container = None


def _container_client():
    global _container
    if _container is None:
        from azure.storage.blob import BlobServiceClient  # lazy

        if not config.AZURE_STORAGE_CONNECTION_STRING:
            raise RuntimeError(
                "STORAGE_BACKEND=azure_blob but AZURE_STORAGE_CONNECTION_STRING is not set"
            )
        svc = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING)
        cc = svc.get_container_client(config.AZURE_BLOB_CONTAINER)
        try:
            cc.create_container()
        except Exception:
            pass  # already exists
        _container = cc
    return _container


def _blob_name(corpus_id: str, name: str) -> str:
    return f"{corpus_id}/{name}"


# --------------------------------------------------------------------------- #
# Public API — used by documents_router
# --------------------------------------------------------------------------- #

def save_pdf(corpus_id: str, name: str, data: bytes) -> None:
    """Persist a PDF's bytes for a corpus."""
    if _use_azure():
        _container_client().upload_blob(_blob_name(corpus_id, name), data, overwrite=True)
    else:
        dest = config.PDF_DIR / corpus_id / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def read_pdf(corpus_id: str, name: str) -> bytes | None:
    """Return a stored PDF's bytes, or None if it does not exist."""
    if _use_azure():
        try:
            return _container_client().download_blob(_blob_name(corpus_id, name)).readall()
        except Exception:
            return None
    p = config.PDF_DIR / corpus_id / name
    return p.read_bytes() if p.is_file() else None


def delete_pdf(corpus_id: str, name: str) -> None:
    if _use_azure():
        try:
            _container_client().delete_blob(_blob_name(corpus_id, name))
        except Exception:
            pass
    else:
        (config.PDF_DIR / corpus_id / name).unlink(missing_ok=True)


def delete_corpus_pdfs(corpus_id: str) -> None:
    """Remove every PDF belonging to a corpus (called on corpus delete)."""
    if _use_azure():
        cc = _container_client()
        for b in cc.list_blobs(name_starts_with=f"{corpus_id}/"):
            try:
                cc.delete_blob(b.name)
            except Exception:
                pass
    else:
        d = config.PDF_DIR / corpus_id
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)

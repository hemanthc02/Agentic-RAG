"""System endpoints: health, config, online/offline status."""

from __future__ import annotations

import asyncio
import os

import httpx
from fastapi import APIRouter

import config
from app import __version__ as APP_VERSION

router = APIRouter(prefix="/api", tags=["system"])

_PING_URLS = {
    "groq": "https://api.groq.com",
}


@router.get("/health")
def health():
    return {"status": "ok", "version": APP_VERSION}


@router.get("/config")
def get_config():
    return {
        "default_mode": config.LLM_MODE,
        "default_provider": config.LLM_PROVIDER,
        "available_providers": {
            "cloud": ["groq"],
            "local": ["ollama"],
        },
        "provider_models": {
            "groq": config.GROQ_MODEL,
            "ollama": config.OLLAMA_MODEL,
        },
        "faithfulness_threshold": config.CITATION_FAITHFULNESS_THRESHOLD,
        "retrieval_relevance_threshold": config.RETRIEVAL_RELEVANCE_THRESHOLD,
        "max_verifier_retries": config.MAX_VERIFIER_RETRIES,
        "embedding_model": config.EMBEDDING_MODEL,
        "nli_model": config.NLI_MODEL,
        "max_pdfs_per_corpus": 20,
        "score_green_min": 0.8,
        "score_amber_min": config.CITATION_FAITHFULNESS_THRESHOLD,
    }


@router.get("/status")
async def network_status():
    """Check reachability of each cloud provider (non-blocking)."""
    results: dict[str, bool] = {}

    async def ping(name: str, url: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(url)
                results[name] = r.status_code < 500
        except Exception:
            results[name] = False

    await asyncio.gather(*[ping(n, u) for n, u in _PING_URLS.items()])

    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{config.OLLAMA_HOST}/api/tags")
            ollama_ok = r.status_code == 200
            ollama_models = [m["name"] for m in r.json().get("models", [])][:10]
    except Exception:
        ollama_ok = False
        ollama_models = []

    return {
        "cloud": results,
        "local": {"ollama": ollama_ok, "models": ollama_models},
        "any_cloud": any(results.values()),
        "ollama_available": ollama_ok,
    }

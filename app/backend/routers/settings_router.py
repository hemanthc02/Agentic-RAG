"""User settings — LLM mode, provider, API keys, Ollama config."""

from __future__ import annotations

import os
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.backend import auth
from app.backend import database as db

router = APIRouter(prefix="/api", tags=["settings"])


class SaveSettingsRequest(BaseModel):
    llm_mode: str = Field(default="cloud", pattern="^(cloud|local)$")
    provider: str = Field(default="groq", pattern="^(groq|ollama)$")
    ollama_host: str = Field(default="http://localhost", max_length=200)
    ollama_port: int = Field(default=11434, ge=1, le=65535)
    ollama_model: str = Field(default="phi3:mini", max_length=100)
    groq_model: str = Field(default="meta-llama/llama-4-scout-17b-16e-instruct", max_length=200)
    groq_api_key: str = Field(default="", max_length=500)


def _mask_key(key: str) -> str:
    if len(key) < 8:
        return "•" * len(key)
    return key[:4] + "•" * (len(key) - 8) + key[-4:]


@router.get("/settings")
def get_settings(user: Annotated[dict, Depends(auth.get_current_user)]):
    s = db.get_user_settings(user["id"])
    # Never expose the raw key — mask it
    s["groq_api_key_masked"] = _mask_key(s.get("groq_api_key", ""))
    s["groq_api_key"] = ""  # clear — frontend uses masked display only
    return s


@router.put("/settings")
def save_settings(
    req: SaveSettingsRequest,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    # If frontend sends empty key, preserve the existing one
    existing = db.get_user_settings(user["id"])
    key_to_save = req.groq_api_key if req.groq_api_key.strip() else existing.get("groq_api_key", "")

    saved = db.save_user_settings(
        user_id=user["id"],
        llm_mode=req.llm_mode,
        provider=req.provider,
        ollama_host=req.ollama_host,
        ollama_port=req.ollama_port,
        ollama_model=req.ollama_model,
        groq_model=req.groq_model,
        groq_api_key=key_to_save,
    )
    saved["groq_api_key_masked"] = _mask_key(saved.get("groq_api_key", ""))
    saved["groq_api_key"] = ""
    return saved


@router.post("/settings/test-ollama")
async def test_ollama(
    user: Annotated[dict, Depends(auth.get_current_user)],
    host: str = "http://localhost",
    port: int = 11434,
):
    url = f"{host}:{port}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(url)
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                return {"ok": True, "models": models}
            return {"ok": False, "models": [], "error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"ok": False, "models": [], "error": str(e)}


@router.post("/settings/test-groq")
async def test_groq(
    user: Annotated[dict, Depends(auth.get_current_user)],
    api_key: str = "",
):
    # Use stored key if none passed
    if not api_key.strip():
        stored = db.get_user_settings(user["id"])
        api_key = stored.get("groq_api_key", "")
    if not api_key.strip():
        return {"ok": False, "error": "No API key configured"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if r.status_code == 200:
                models = [m["id"] for m in r.json().get("data", [])][:10]
                return {"ok": True, "models": models}
            return {"ok": False, "error": f"HTTP {r.status_code}: invalid key"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

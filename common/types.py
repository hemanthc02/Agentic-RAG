"""Canonical shared types — single source of truth for the whole monorepo.

All enums and Pydantic models used by more than one package/service are defined
here. Other modules import from here; they never redefine these types locally.

Import path from repo root:
    from common.types import LLMMode, ProviderName, CitedChunk
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LLMMode(str, Enum):
    """High-level inference tier: cloud API vs local daemon."""

    cloud = "cloud"
    local = "local"


class ProviderName(str, Enum):
    """Specific LLM provider / backend identifier."""

    groq = "groq"
    gemini = "gemini"
    openrouter = "openrouter"
    nvidia_nim = "nvidia_nim"
    ollama = "ollama"


# ---------------------------------------------------------------------------
# Shared Pydantic model
# ---------------------------------------------------------------------------

class CitedChunk(BaseModel):
    """A retrieved corpus chunk with provenance info surfaced to the UI."""

    chunk_id: str
    source: str = Field(..., description="Source PDF filename")
    page: int
    text: str = Field(..., description="Chunk excerpt shown in the UI")
    score: float | None = Field(default=None, description="Retrieval similarity score")

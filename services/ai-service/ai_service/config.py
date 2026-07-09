"""Typed, env-driven configuration for the AI layer (12-factor).

Secrets come from the environment only — never hard-coded, never persisted in
the database (the DB stores a ``secret_ref``, not the key itself).

``ProviderName`` is imported from ``common.types`` (the repo-wide canonical
source) so the enum is defined exactly once across the monorepo.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Expose repo root so ``common.types`` is importable whether this service is
# run from the monorepo root or from its own directory.
_ROOT = Path(__file__).resolve().parents[3]  # services/ai-service/ai_service/ -> repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pydantic import Field  # noqa: E402
from pydantic_settings import BaseSettings, SettingsConfigDict  # noqa: E402

from common.types import LLMMode, ProviderName  # noqa: E402

# Re-export so existing ``from ai_service.config import ProviderName`` imports
# keep working without any change to factory.py or other callers.
__all__ = ["AISettings", "LLMMode", "ProviderName", "get_settings"]


class AISettings(BaseSettings):
    """Loaded from environment / .env. Prefix-free names match the PRD example."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Selection
    llm_mode: LLMMode = LLMMode.cloud
    llm_provider: ProviderName = ProviderName.gemini

    # Shared HTTP behaviour
    request_timeout_s: float = 60.0
    max_attempts: int = 3
    backoff_seconds: tuple[int, ...] = (1, 2, 4)

    # Gemini
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # OpenRouter (OpenAI-compatible)
    openrouter_api_key: str | None = None
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # NVIDIA NIM (OpenAI-compatible)
    nvidia_nim_api_key: str | None = None
    nvidia_nim_model: str = "meta/llama-3.3-70b-instruct"
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"

    # Ollama (local; no key)
    ollama_model: str = "phi3:mini"
    ollama_base_url: str = "http://localhost:11434"


def get_settings() -> AISettings:
    return AISettings()

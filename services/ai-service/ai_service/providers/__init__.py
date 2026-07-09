"""Concrete LLM providers."""

from ai_service.providers.gemini import GeminiProvider
from ai_service.providers.ollama import OllamaProvider
from ai_service.providers.openai_compat import (
    NvidiaNIMProvider,
    OpenRouterProvider,
)

__all__ = [
    "GeminiProvider",
    "OpenRouterProvider",
    "NvidiaNIMProvider",
    "OllamaProvider",
]

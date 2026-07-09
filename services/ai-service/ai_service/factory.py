"""Provider factory — switch LLM backends purely by configuration.

This is the single place that knows about concrete providers. Agents call
``LLMProviderFactory.from_settings(...)`` (or inject the resulting
``LLMProvider``) and never import a concrete class — satisfying the
Dependency-Inversion and Open/Closed principles. Adding a provider = register
one builder here; no agent changes.
"""

from __future__ import annotations

from collections.abc import Callable

from ai_service.base import LLMProvider, ProviderConfigError
from ai_service.config import AISettings, ProviderName, get_settings
from ai_service.providers import (
    GeminiProvider,
    NvidiaNIMProvider,
    OllamaProvider,
    OpenRouterProvider,
)


def _build_gemini(s: AISettings) -> LLMProvider:
    return GeminiProvider(api_key=s.gemini_api_key, model=s.gemini_model,
                          base_url=s.gemini_base_url, timeout_s=s.request_timeout_s)


def _build_openrouter(s: AISettings) -> LLMProvider:
    return OpenRouterProvider(api_key=s.openrouter_api_key, model=s.openrouter_model,
                              base_url=s.openrouter_base_url, timeout_s=s.request_timeout_s)


def _build_nvidia(s: AISettings) -> LLMProvider:
    return NvidiaNIMProvider(api_key=s.nvidia_nim_api_key, model=s.nvidia_nim_model,
                             base_url=s.nvidia_nim_base_url, timeout_s=s.request_timeout_s)


def _build_ollama(s: AISettings) -> LLMProvider:
    return OllamaProvider(model=s.ollama_model, base_url=s.ollama_base_url,
                          timeout_s=s.request_timeout_s)


_REGISTRY: dict[ProviderName, Callable[[AISettings], LLMProvider]] = {
    ProviderName.gemini: _build_gemini,
    ProviderName.openrouter: _build_openrouter,
    ProviderName.nvidia_nim: _build_nvidia,
    ProviderName.ollama: _build_ollama,
}


class LLMProviderFactory:
    @staticmethod
    def create(provider: ProviderName, settings: AISettings | None = None) -> LLMProvider:
        settings = settings or get_settings()
        builder = _REGISTRY.get(provider)
        if builder is None:  # pragma: no cover - guarded by enum
            raise ProviderConfigError(f"unknown provider: {provider}")
        return builder(settings)

    @staticmethod
    def from_settings(settings: AISettings | None = None) -> LLMProvider:
        """Resolve the active provider: local mode → Ollama, else configured provider."""
        settings = settings or get_settings()
        if settings.llm_mode == "local":
            return _build_ollama(settings)
        return LLMProviderFactory.create(settings.llm_provider, settings)

    @staticmethod
    def available() -> list[str]:
        return [p.value for p in _REGISTRY]

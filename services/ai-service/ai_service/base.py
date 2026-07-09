"""The unified LLM provider interface and its error taxonomy.

Every concrete provider (Gemini, OpenRouter, NVIDIA NIM, Ollama) implements
``LLMProvider``. Application/agent code depends ONLY on this abstraction
(Dependency Inversion) — switching providers is a configuration change, never a
code change in the agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from ai_service.types import Completion, GenerationParams, Message


class LLMError(Exception):
    """Base class for all provider errors (lets callers catch one type)."""


class ProviderConfigError(LLMError):
    """Missing/invalid configuration (e.g., no API key)."""


class ProviderAuthError(LLMError):
    """Authentication/authorization failure (401/403)."""


class ProviderRateLimitError(LLMError):
    """Rate limited (429) — retryable with backoff."""


class ProviderTimeoutError(LLMError):
    """Network or server timeout — retryable."""


class ProviderResponseError(LLMError):
    """Malformed or unexpected provider response."""


# Errors worth retrying with exponential backoff.
RETRYABLE: tuple[type[LLMError], ...] = (ProviderRateLimitError, ProviderTimeoutError)


class LLMProvider(ABC):
    """Abstract base every provider implements.

    Attributes:
        name: stable provider identifier (e.g. ``"gemini"``).
        model: default model id used when a call does not override it.
        supports_streaming: whether ``stream`` yields incremental tokens.
    """

    name: str
    model: str
    supports_streaming: bool = True

    @abstractmethod
    async def complete(
        self, messages: list[Message], params: GenerationParams | None = None
    ) -> Completion:
        """Return a full completion for the given chat messages."""

    @abstractmethod
    def stream(
        self, messages: list[Message], params: GenerationParams | None = None
    ) -> AsyncIterator[str]:
        """Yield text deltas as they arrive. Implement as an async generator."""

    async def generate(
        self,
        messages: list[Message],
        *,
        params: GenerationParams | None = None,
        stream: bool = False,
    ) -> Completion | AsyncIterator[str]:
        """Convenience dispatch matching the SDD's documented signature."""
        if stream:
            return self.stream(messages, params)
        return await self.complete(messages, params)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<{type(self).__name__} name={self.name!r} model={self.model!r}>"

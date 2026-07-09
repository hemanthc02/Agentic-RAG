"""Swappable LLM backend abstraction.

Every LLM call in the research stack goes through this interface — agents and
the baseline never call a provider SDK directly. Selection is by
``config.LLM_MODE`` (cloud | local) and ``config.LLM_PROVIDER`` (groq | ollama).

The app ships exactly two models:
    groq      — cloud, Groq API: Llama 4 Scout 17B (fast, free tier available)
    ollama    — local daemon: Phi-3 mini (no cloud call, fully on-device)

(The standalone ``services/ai-service`` library retains broader provider support
for future work; this research module intentionally offers only the two above.)
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

import config

logger = logging.getLogger(__name__)


class LLMBackendError(RuntimeError):
    """Raised when an LLM backend call fails after all retries."""


class LLMBackend(ABC):
    """Abstract LLM backend. Agents depend on this, not on a provider SDK."""

    name: str

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        temperature: float = config.DEFAULT_TEMPERATURE,
        max_tokens: int = config.DEFAULT_MAX_TOKENS,
    ) -> str:
        """Return the model's text completion for ``prompt``."""


def _with_retry(
    call,
    *,
    attempts: int = config.MAX_LLM_ATTEMPTS,
    backoff: tuple[int, ...] = config.RETRY_BACKOFF_SECONDS,
) -> str:
    """Run ``call`` with exponential backoff on transient failures."""
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as exc:
            last = exc
            if attempt == attempts:
                break
            delay = backoff[min(attempt - 1, len(backoff) - 1)]
            logger.warning(
                "LLM call failed (%d/%d): %s; retry in %ss", attempt, attempts, exc, delay
            )
            time.sleep(delay)
    raise LLMBackendError(f"LLM call failed after {attempts} attempts: {last}") from last


class GroqBackend(LLMBackend):
    """Cloud backend using Groq's API. Requires ``GROQ_API_KEY``."""

    name = "groq"

    def __init__(self, model: str = config.GROQ_MODEL, api_key: str | None = None) -> None:
        self.model = model
        self._api_key = api_key or config.GROQ_API_KEY
        if not self._api_key:
            raise LLMBackendError("GROQ_API_KEY is not set")
        self._client = None  # lazy-init

    def _client_or_init(self):
        if self._client is None:
            from groq import Groq  # lazy import

            self._client = Groq(api_key=self._api_key)
        return self._client

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = config.DEFAULT_TEMPERATURE,
        max_tokens: int = config.DEFAULT_MAX_TOKENS,
    ) -> str:
        client = self._client_or_init()

        def _call() -> str:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""

        return _with_retry(_call)


class OllamaBackend(LLMBackend):
    """Local backend using an Ollama daemon. Nothing leaves the device."""

    name = "ollama"

    def __init__(self, model: str = config.OLLAMA_MODEL, host: str = config.OLLAMA_HOST) -> None:
        self.model = model
        self._host = host.rstrip("/")

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = config.DEFAULT_TEMPERATURE,
        max_tokens: int = config.DEFAULT_MAX_TOKENS,
    ) -> str:
        import httpx  # lazy import

        def _call() -> str:
            resp = httpx.post(
                f"{self._host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
                timeout=config.OLLAMA_TIMEOUT_S,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")

        return _with_retry(_call)


def get_backend(
    mode: str | None = None, provider: str | None = None
) -> LLMBackend:
    """Return the configured LLM backend.

    Resolution order:
      1. ``mode="local"``  → OllamaBackend (regardless of provider)
      2. ``provider``      → route to that specific backend
      3. ``config.LLM_MODE / config.LLM_PROVIDER`` defaults

    Supported providers in the research stack: "groq", "ollama".
    """
    resolved_mode = (mode or config.LLM_MODE).lower()
    resolved_provider = (provider or config.LLM_PROVIDER).lower()

    if resolved_mode == "local" or resolved_provider == "ollama":
        return OllamaBackend()
    if resolved_provider == "groq":
        return GroqBackend()

    raise LLMBackendError(
        f"Provider {resolved_provider!r} is not available. The app offers two "
        "models only: 'groq' (cloud, Llama 4 Scout 17B) or 'ollama' (local, Phi-3 mini)."
    )

"""Provider base for OpenAI-compatible chat APIs (OpenRouter, NVIDIA NIM).

Both expose the `/chat/completions` schema, so they share one implementation
and differ only by base URL, key, and default model. ``httpx`` is imported
lazily so the module (and the factory/tests) import without the dependency or
network present.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from ai_service.base import (
    LLMProvider,
    ProviderAuthError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from ai_service.types import Completion, GenerationParams, Message, Usage


class OpenAICompatProvider(LLMProvider):
    supports_streaming = True

    def __init__(self, *, name: str, base_url: str, api_key: str | None, model: str,
                 timeout_s: float = 60.0, extra_headers: dict[str, str] | None = None) -> None:
        if not api_key:
            raise ProviderConfigError(f"{name}: API key is required")
        self.name = name
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_s
        self._extra_headers = extra_headers or {}

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json", **self._extra_headers}

    def _payload(self, messages: list[Message], params: GenerationParams, stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
            "temperature": params.temperature,
            "max_tokens": params.max_tokens,
            "top_p": params.top_p,
            "stop": params.stop,
            "stream": stream,
        }

    @staticmethod
    def _raise_for_status(status: int, body: str) -> None:
        if status in (401, 403):
            raise ProviderAuthError(f"auth failed ({status}): {body[:200]}")
        if status == 429:
            raise ProviderRateLimitError(f"rate limited: {body[:200]}")
        if status >= 500:
            raise ProviderTimeoutError(f"server error {status}: {body[:200]}")
        if status >= 400:
            raise ProviderResponseError(f"bad request {status}: {body[:200]}")

    async def complete(self, messages: list[Message],
                       params: GenerationParams | None = None) -> Completion:
        import httpx  # lazy

        params = params or GenerationParams()
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base_url}/chat/completions",
                                         headers=self._headers(),
                                         json=self._payload(messages, params, stream=False))
        except httpx.TimeoutException as exc:  # pragma: no cover - network
            raise ProviderTimeoutError(str(exc)) from exc
        self._raise_for_status(resp.status_code, resp.text)
        data = resp.json()
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"]
            usage = data.get("usage", {})
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError(f"unexpected response: {data}") from exc
        return Completion(
            text=text, provider=self.name, model=data.get("model", self.model),
            finish_reason=choice.get("finish_reason"),
            usage=Usage(prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        total_tokens=usage.get("total_tokens", 0)),
            latency_ms=int((time.perf_counter() - t0) * 1000))

    async def stream(self, messages: list[Message],
                     params: GenerationParams | None = None) -> AsyncIterator[str]:
        import json
        import httpx  # lazy

        params = params or GenerationParams()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream("POST", f"{self._base_url}/chat/completions",
                                         headers=self._headers(),
                                         json=self._payload(messages, params, stream=True)) as resp:
                    self._raise_for_status(resp.status_code, "")
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        chunk = line[len("data:"):].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            delta = json.loads(chunk)["choices"][0]["delta"].get("content")
                        except (KeyError, IndexError, ValueError):
                            continue
                        if delta:
                            yield delta
        except httpx.TimeoutException as exc:  # pragma: no cover - network
            raise ProviderTimeoutError(str(exc)) from exc


class OpenRouterProvider(OpenAICompatProvider):
    def __init__(self, *, api_key: str | None, model: str, base_url: str,
                 timeout_s: float = 60.0) -> None:
        super().__init__(name="openrouter", base_url=base_url, api_key=api_key,
                         model=model, timeout_s=timeout_s,
                         extra_headers={"HTTP-Referer": "https://veritasrag.local",
                                        "X-Title": "VeritasRAG"})


class NvidiaNIMProvider(OpenAICompatProvider):
    def __init__(self, *, api_key: str | None, model: str, base_url: str,
                 timeout_s: float = 60.0) -> None:
        super().__init__(name="nvidia_nim", base_url=base_url, api_key=api_key,
                         model=model, timeout_s=timeout_s)

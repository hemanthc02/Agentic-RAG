"""Local Ollama provider (the privacy/air-gapped backend).

Talks to a local Ollama daemon (`/api/chat`). No API key; nothing leaves the
device. ``httpx`` imported lazily.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from ai_service.base import LLMProvider, ProviderResponseError, ProviderTimeoutError
from ai_service.types import Completion, GenerationParams, Message, Usage


class OllamaProvider(LLMProvider):
    name = "ollama"
    supports_streaming = True

    def __init__(self, *, model: str, base_url: str, timeout_s: float = 120.0) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s

    def _body(self, messages: list[Message], params: GenerationParams, stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
            "stream": stream,
            "options": {"temperature": params.temperature,
                        "num_predict": params.max_tokens, "top_p": params.top_p},
        }

    async def complete(self, messages: list[Message],
                       params: GenerationParams | None = None) -> Completion:
        import httpx  # lazy

        params = params or GenerationParams()
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base_url}/api/chat",
                                         json=self._body(messages, params, stream=False))
        except httpx.TimeoutException as exc:  # pragma: no cover - network
            raise ProviderTimeoutError(str(exc)) from exc
        if resp.status_code >= 400:
            raise ProviderResponseError(f"ollama error {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        try:
            text = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderResponseError(f"unexpected response: {data}") from exc
        return Completion(
            text=text, provider=self.name, model=self.model,
            finish_reason=data.get("done_reason"),
            usage=Usage(prompt_tokens=data.get("prompt_eval_count", 0),
                        completion_tokens=data.get("eval_count", 0),
                        total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0)),
            latency_ms=int((time.perf_counter() - t0) * 1000))

    async def stream(self, messages: list[Message],
                     params: GenerationParams | None = None) -> AsyncIterator[str]:
        import json
        import httpx  # lazy

        params = params or GenerationParams()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream("POST", f"{self._base_url}/api/chat",
                                         json=self._body(messages, params, stream=True)) as resp:
                    if resp.status_code >= 400:
                        raise ProviderResponseError(f"ollama error {resp.status_code}")
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except ValueError:
                            continue
                        delta = obj.get("message", {}).get("content")
                        if delta:
                            yield delta
                        if obj.get("done"):
                            break
        except httpx.TimeoutException as exc:  # pragma: no cover - network
            raise ProviderTimeoutError(str(exc)) from exc

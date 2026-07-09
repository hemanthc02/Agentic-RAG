"""Google Gemini provider via the Generative Language REST API.

Uses REST (httpx, lazy import) rather than the SDK to keep the dependency
surface small and uniform with the other providers.
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
from ai_service.types import Completion, GenerationParams, Message, Role, Usage


class GeminiProvider(LLMProvider):
    name = "gemini"
    supports_streaming = True

    def __init__(self, *, api_key: str | None, model: str, base_url: str,
                 timeout_s: float = 60.0) -> None:
        if not api_key:
            raise ProviderConfigError("gemini: API key is required")
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s

    def _to_contents(self, messages: list[Message]) -> tuple[list[dict], str | None]:
        """Gemini separates a system instruction from role-tagged contents."""
        system = next((m.content for m in messages if m.role == Role.system), None)
        contents = [
            {"role": "model" if m.role == Role.assistant else "user",
             "parts": [{"text": m.content}]}
            for m in messages if m.role != Role.system
        ]
        return contents, system

    def _body(self, messages: list[Message], params: GenerationParams) -> dict:
        contents, system = self._to_contents(messages)
        body: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": params.temperature,
                "maxOutputTokens": params.max_tokens,
                "topP": params.top_p,
                **({"stopSequences": params.stop} if params.stop else {}),
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        return body

    @staticmethod
    def _raise_for_status(status: int, text: str) -> None:
        if status in (401, 403):
            raise ProviderAuthError(f"auth failed ({status}): {text[:200]}")
        if status == 429:
            raise ProviderRateLimitError(f"rate limited: {text[:200]}")
        if status >= 500:
            raise ProviderTimeoutError(f"server error {status}: {text[:200]}")
        if status >= 400:
            raise ProviderResponseError(f"bad request {status}: {text[:200]}")

    async def complete(self, messages: list[Message],
                       params: GenerationParams | None = None) -> Completion:
        import httpx  # lazy

        params = params or GenerationParams()
        url = f"{self._base_url}/models/{self.model}:generateContent?key={self._api_key}"
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=self._body(messages, params))
        except httpx.TimeoutException as exc:  # pragma: no cover - network
            raise ProviderTimeoutError(str(exc)) from exc
        self._raise_for_status(resp.status_code, resp.text)
        data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
            finish = data["candidates"][0].get("finishReason")
            um = data.get("usageMetadata", {})
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError(f"unexpected response: {data}") from exc
        return Completion(
            text=text, provider=self.name, model=self.model, finish_reason=finish,
            usage=Usage(prompt_tokens=um.get("promptTokenCount", 0),
                        completion_tokens=um.get("candidatesTokenCount", 0),
                        total_tokens=um.get("totalTokenCount", 0)),
            latency_ms=int((time.perf_counter() - t0) * 1000))

    async def stream(self, messages: list[Message],
                     params: GenerationParams | None = None) -> AsyncIterator[str]:
        import json
        import httpx  # lazy

        params = params or GenerationParams()
        url = (f"{self._base_url}/models/{self.model}:streamGenerateContent"
               f"?alt=sse&key={self._api_key}")
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream("POST", url, json=self._body(messages, params)) as resp:
                    self._raise_for_status(resp.status_code, "")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        try:
                            obj = json.loads(line[len("data:"):].strip())
                            parts = obj["candidates"][0]["content"]["parts"]
                        except (KeyError, IndexError, ValueError):
                            continue
                        for p in parts:
                            if p.get("text"):
                                yield p["text"]
        except httpx.TimeoutException as exc:  # pragma: no cover - network
            raise ProviderTimeoutError(str(exc)) from exc

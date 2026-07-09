# ai-service — provider-agnostic LLM layer

The keystone of the AI architecture. Agents depend on the `LLMProvider`
abstraction only; switching backends is configuration, not code.

```python
from ai_service import LLMProviderFactory, Message, Role

provider = LLMProviderFactory.from_settings()        # local→Ollama, else configured
completion = await provider.complete([Message(role=Role.user, content="Hello")])
print(completion.text, completion.provider, completion.usage)
```

Providers: `GeminiProvider`, `OpenRouterProvider`, `NvidiaNIMProvider`, `OllamaProvider`.
Add a provider = one adapter + one registry entry in `factory.py` (Open/Closed).

Config via env (see `.env.example`): `LLM_MODE`, `LLM_PROVIDER`, per-provider keys/models.
Resilience: retry with backoff (1,2,4 s ×3) on rate-limit/timeout; fail-fast on auth/config.

Dev: `pip install -e ".[dev]" && pytest`.

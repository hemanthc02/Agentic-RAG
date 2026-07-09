"""Unit tests for the LLM provider abstraction + factory (no network)."""

from __future__ import annotations

import pytest

from ai_service.base import LLMProvider, ProviderConfigError
from ai_service.config import AISettings, ProviderName
from ai_service.factory import LLMProviderFactory


def _settings(**kw) -> AISettings:
    base = dict(
        gemini_api_key="k", openrouter_api_key="k", nvidia_nim_api_key="k",
    )
    base.update(kw)
    return AISettings(**base)


def test_available_lists_all_four():
    assert set(LLMProviderFactory.available()) == {
        "gemini", "openrouter", "nvidia_nim", "ollama"
    }


@pytest.mark.parametrize("provider,expected", [
    (ProviderName.gemini, "gemini"),
    (ProviderName.openrouter, "openrouter"),
    (ProviderName.nvidia_nim, "nvidia_nim"),
    (ProviderName.ollama, "ollama"),
])
def test_create_returns_provider(provider, expected):
    p = LLMProviderFactory.create(provider, _settings())
    assert isinstance(p, LLMProvider)
    assert p.name == expected
    assert p.model  # default model set


def test_from_settings_local_mode_uses_ollama():
    p = LLMProviderFactory.from_settings(_settings(llm_mode="local"))
    assert p.name == "ollama"


def test_from_settings_cloud_mode_uses_configured_provider():
    p = LLMProviderFactory.from_settings(
        _settings(llm_mode="cloud", llm_provider=ProviderName.openrouter)
    )
    assert p.name == "openrouter"


def test_missing_key_raises_config_error():
    with pytest.raises(ProviderConfigError):
        LLMProviderFactory.create(ProviderName.gemini, AISettings(gemini_api_key=None))


def test_agents_depend_only_on_abstraction():
    # The returned object satisfies the LLMProvider interface used by agents.
    p = LLMProviderFactory.create(ProviderName.nvidia_nim, _settings())
    assert hasattr(p, "complete") and hasattr(p, "stream") and hasattr(p, "generate")

"""Tests for the LLM provider seam (factory + OpenAI/Anthropic/Google)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from app.llm import client as client_module
from app.llm import factory as factory_module
from app.llm.models import QuestionClassification
from app.llm.providers.anthropic import AnthropicProvider
from app.llm.providers.google import GoogleProvider
from app.llm.providers.openai import OpenAIProvider
from app.llm.roles import LLMRole


@pytest.fixture(autouse=True)
def _reset_factory_cache() -> None:
    factory_module.reset_provider_cache()
    yield
    factory_module.reset_provider_cache()


@pytest.fixture
def mock_create(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(client_module.client.chat.completions, "create", mock)
    return mock


# --- factory selection ------------------------------------------------------


def test_factory_rejects_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_module.settings, "llm_provider", "bogus")
    with pytest.raises(RuntimeError, match="Unsupported LLM provider"):
        factory_module.get_provider()


def test_factory_rejects_github(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_module.settings, "llm_provider", "github")
    with pytest.raises(RuntimeError, match="only valid for non-github"):
        factory_module.get_provider()


def test_factory_returns_openai_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module.settings, "llm_provider", "openai")
    monkeypatch.setattr(
        client_module.settings, "openai_api_key", SecretStr("sk-test")
    )
    provider = factory_module.get_provider()
    assert isinstance(provider, OpenAIProvider)
    assert provider.name == "openai"


def test_factory_returns_anthropic_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module.settings, "llm_provider", "anthropic")
    monkeypatch.setattr(
        client_module.settings, "anthropic_api_key", SecretStr("sk-ant")
    )
    provider = factory_module.get_provider()
    assert isinstance(provider, AnthropicProvider)


def test_factory_returns_google_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module.settings, "llm_provider", "google")
    monkeypatch.setattr(
        client_module.settings, "google_api_key", SecretStr("g-key")
    )
    provider = factory_module.get_provider()
    assert isinstance(provider, GoogleProvider)


def test_factory_raises_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module.settings, "llm_provider", "anthropic")
    monkeypatch.setattr(client_module.settings, "anthropic_api_key", None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        factory_module.get_provider()


def test_factory_caches_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_module.settings, "llm_provider", "openai")
    monkeypatch.setattr(
        client_module.settings, "openai_api_key", SecretStr("sk-test")
    )
    p1 = factory_module.get_provider()
    p2 = factory_module.get_provider()
    assert p1 is p2


# --- provider.complete wiring ----------------------------------------------


@pytest.mark.asyncio
async def test_openai_provider_passes_correct_kwargs(
    monkeypatch: pytest.MonkeyPatch, mock_create: AsyncMock
) -> None:
    monkeypatch.setattr(
        client_module.settings, "openai_api_key", SecretStr("sk-test")
    )
    monkeypatch.setattr(client_module.settings, "openai_model", "gpt-5.4")
    expected = QuestionClassification(
        question_type="factual", rationale="ok", answerable=True
    )
    mock_create.return_value = expected

    provider = OpenAIProvider()
    result = await provider.complete(
        role=LLMRole.CLASSIFIER,
        messages=[{"role": "user", "content": "hi"}],
        response_model=QuestionClassification,
        temperature=0.0,
        max_tokens=512,
    )

    assert result is expected
    kwargs = mock_create.call_args.kwargs
    assert kwargs["model"] == "gpt-5.4"
    assert kwargs["custom_llm_provider"] == "openai"
    assert kwargs["api_key"] == "sk-test"
    assert kwargs["temperature"] == 0.0
    assert kwargs["max_tokens"] == 512
    assert kwargs["response_model"] is QuestionClassification


@pytest.mark.asyncio
async def test_anthropic_provider_uses_anthropic_tag(
    monkeypatch: pytest.MonkeyPatch, mock_create: AsyncMock
) -> None:
    monkeypatch.setattr(
        client_module.settings, "anthropic_api_key", SecretStr("sk-ant")
    )
    mock_create.return_value = QuestionClassification(
        question_type="factual", rationale="ok", answerable=True
    )
    provider = AnthropicProvider()
    await provider.complete(
        role=LLMRole.CLASSIFIER,
        messages=[{"role": "user", "content": "hi"}],
        response_model=QuestionClassification,
        temperature=0.0,
        max_tokens=512,
    )
    kwargs = mock_create.call_args.kwargs
    assert kwargs["custom_llm_provider"] == "anthropic"
    assert kwargs["api_key"] == "sk-ant"
    assert kwargs["model"] == client_module.settings.anthropic_model


@pytest.mark.asyncio
async def test_google_provider_uses_gemini_tag(
    monkeypatch: pytest.MonkeyPatch, mock_create: AsyncMock
) -> None:
    monkeypatch.setattr(
        client_module.settings, "google_api_key", SecretStr("g-key")
    )
    mock_create.return_value = QuestionClassification(
        question_type="factual", rationale="ok", answerable=True
    )
    provider = GoogleProvider()
    await provider.complete(
        role=LLMRole.CLASSIFIER,
        messages=[{"role": "user", "content": "hi"}],
        response_model=QuestionClassification,
        temperature=0.0,
        max_tokens=512,
    )
    kwargs = mock_create.call_args.kwargs
    assert kwargs["custom_llm_provider"] == "gemini"
    assert kwargs["api_key"] == "g-key"


@pytest.mark.asyncio
async def test_per_role_override_takes_precedence(
    monkeypatch: pytest.MonkeyPatch, mock_create: AsyncMock
) -> None:
    monkeypatch.setattr(
        client_module.settings, "openai_api_key", SecretStr("sk-test")
    )
    monkeypatch.setattr(client_module.settings, "openai_model", "gpt-5.4")
    monkeypatch.setattr(
        client_module.settings, "openai_model_synthesizer", "gpt-5.4-turbo"
    )
    mock_create.return_value = QuestionClassification(
        question_type="factual", rationale="ok", answerable=True
    )
    provider = OpenAIProvider()
    assert provider.model_for(LLMRole.CLASSIFIER) == "gpt-5.4"
    assert provider.model_for(LLMRole.SYNTHESIZER) == "gpt-5.4-turbo"


# --- end-to-end: client.call routes through factory ------------------------


@pytest.mark.asyncio
async def test_llm_call_routes_through_provider_for_non_github(
    monkeypatch: pytest.MonkeyPatch, mock_create: AsyncMock
) -> None:
    monkeypatch.setattr(client_module.settings, "llm_provider", "openai")
    monkeypatch.setattr(
        client_module.settings, "openai_api_key", SecretStr("sk-test")
    )
    monkeypatch.setattr(client_module.settings, "openai_model", "gpt-5.4")
    expected = QuestionClassification(
        question_type="factual", rationale="ok", answerable=True
    )
    mock_create.return_value = expected

    # Judge role would normally hit the WP-5 fallback path; with
    # llm_provider=openai we must skip that and go through the factory.
    result = await client_module.llm.call(
        LLMRole.JUDGE,
        [{"role": "user", "content": "evaluate"}],
        QuestionClassification,
    )

    assert result is expected
    kwargs = mock_create.call_args.kwargs
    assert kwargs["custom_llm_provider"] == "openai"
    assert kwargs["api_key"] == "sk-test"
    # No api_base — that is github-only.
    assert "api_base" not in kwargs or kwargs.get("api_base") is None


@pytest.mark.asyncio
async def test_llm_call_github_path_unchanged(
    monkeypatch: pytest.MonkeyPatch, mock_create: AsyncMock
) -> None:
    """Sanity: leaving llm_provider=github keeps the legacy GitHub Models path."""
    monkeypatch.setattr(client_module.settings, "llm_provider", "github")
    expected = QuestionClassification(
        question_type="factual", rationale="ok", answerable=True
    )
    mock_create.return_value = expected

    await client_module.llm.call(
        LLMRole.CLASSIFIER,
        [{"role": "user", "content": "hi"}],
        QuestionClassification,
    )
    kwargs: dict[str, Any] = mock_create.call_args.kwargs
    # GitHub path always sets api_base to the GitHub Models endpoint.
    assert kwargs["api_base"] == client_module.settings.llm_api_base
    assert kwargs["custom_llm_provider"] == "openai"

"""Tests for the runtime LLM provider selection seam."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from pydantic import SecretStr

from app.domain.enums import OutputFormat
from app.domain.run import RunCreate
from app.llm import client as client_module
from app.llm import factory as factory_module
from app.llm.client import current_provider, resolve_active_provider
from app.llm.models import QuestionClassification
from app.llm.roles import LLMRole


@pytest.fixture(autouse=True)
def _reset_factory_cache() -> None:
    factory_module.reset_provider_cache()
    yield
    factory_module.reset_provider_cache()


# --- RunCreate validation ---------------------------------------------------


def test_run_create_default_provider_is_github() -> None:
    rc = RunCreate(
        question="What is event sourcing in distributed systems?",
        user_context=None,
        output_format=OutputFormat.PROSE,
        confidence_threshold=0.7,
    )
    assert rc.llm_provider == "github"


def test_run_create_accepts_known_providers() -> None:
    for name in ("github", "openai", "anthropic", "google"):
        rc = RunCreate(
            question="Long enough question for validation.",
            llm_provider=name,
        )
        assert rc.llm_provider == name


def test_run_create_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="llm_provider must be one of"):
        RunCreate(
            question="Long enough question for validation.",
            llm_provider="cohere",
        )


# --- contextvar override ----------------------------------------------------


def test_resolve_active_provider_uses_contextvar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module.settings, "llm_provider", "github")
    assert resolve_active_provider() == "github"
    tok = current_provider.set("anthropic")
    try:
        assert resolve_active_provider() == "anthropic"
    finally:
        current_provider.reset(tok)
    assert resolve_active_provider() == "github"


@pytest.mark.asyncio
async def test_llm_call_honours_contextvar_over_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Settings say github (the legacy path), but the contextvar pins openai.
    monkeypatch.setattr(client_module.settings, "llm_provider", "github")
    monkeypatch.setattr(
        client_module.settings, "openai_api_key", SecretStr("sk-test")
    )
    monkeypatch.setattr(client_module.settings, "openai_model", "gpt-5.4")

    expected = QuestionClassification(
        question_type="factual", rationale="ok", answerable=True
    )
    mock = AsyncMock(return_value=expected)
    monkeypatch.setattr(client_module.client.chat.completions, "create", mock)

    tok = current_provider.set("openai")
    try:
        result = await client_module.llm.call(
            LLMRole.CLASSIFIER,
            [{"role": "user", "content": "hi"}],
            QuestionClassification,
        )
    finally:
        current_provider.reset(tok)

    assert result is expected
    kwargs: dict[str, Any] = mock.call_args.kwargs
    assert kwargs["custom_llm_provider"] == "openai"
    assert kwargs["api_key"] == "sk-test"


# --- GET /api/llm/providers -------------------------------------------------


@pytest.mark.asyncio
async def test_providers_endpoint_lists_all_with_availability(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(client_module.settings, "openai_api_key", SecretStr("x"))
    monkeypatch.setattr(client_module.settings, "anthropic_api_key", None)
    monkeypatch.setattr(client_module.settings, "google_api_key", None)

    res = await client.get("/api/llm/providers")
    assert res.status_code == 200
    body = res.json()
    assert body["default"] == "github"
    names = {p["name"]: p for p in body["providers"]}
    assert set(names) == {"github", "openai", "anthropic", "google"}
    assert names["github"]["available"] is True
    assert names["openai"]["available"] is True
    assert names["anthropic"]["available"] is False
    assert names["google"]["available"] is False


# --- create_run persists the provider --------------------------------------


@pytest.mark.asyncio
async def test_create_run_persists_llm_provider(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    res = await client.post(
        "/api/runs",
        json={
            "question": "What is event sourcing in distributed systems?",
            "llm_provider": "anthropic",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["llm_provider"] == "anthropic"

    # Confirm GET round-trips it.
    res2 = await client.get(f"/api/runs/{body['id']}")
    assert res2.status_code == 200
    assert res2.json()["llm_provider"] == "anthropic"


@pytest.mark.asyncio
async def test_create_run_defaults_to_github_when_unspecified(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    res = await client.post(
        "/api/runs",
        json={"question": "What is event sourcing in distributed systems?"},
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["llm_provider"] == "github"


@pytest.mark.asyncio
async def test_create_run_rejects_unknown_provider(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    res = await client.post(
        "/api/runs",
        json={
            "question": "What is event sourcing in distributed systems?",
            "llm_provider": "cohere",
        },
        headers=auth_headers,
    )
    assert res.status_code in (400, 422)

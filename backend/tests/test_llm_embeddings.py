"""Tests for ``app.llm.embeddings.embed`` provider fallback."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from litellm.exceptions import RateLimitError
from pydantic import SecretStr

from app.llm import embeddings as embeddings_module


def _fake_response(dim: int = 3, count: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        data=[{"embedding": [0.1] * dim} for _ in range(count)],
    )


@pytest.mark.asyncio
async def test_embed_returns_empty_for_empty_input() -> None:
    result = await embeddings_module.embed([])
    assert result == []


@pytest.mark.asyncio
async def test_embed_falls_back_to_github_pool_on_openai_quota_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: OpenAI 429 must NOT block embeddings when GH pool is available."""
    monkeypatch.setattr(
        embeddings_module.settings,
        "openai_api_key",
        SecretStr("sk-dead-quota"),
        raising=False,
    )

    fallback_called = AsyncMock(return_value=_fake_response(dim=3, count=1))
    monkeypatch.setattr(embeddings_module, "_TOKEN_POOL", ("ghp_1", "ghp_2"))
    monkeypatch.setattr(
        embeddings_module,
        "_call_with_token_fallback",
        fallback_called,
    )

    rate_limit = RateLimitError(
        message="429 insufficient_quota", llm_provider="openai", model="x"
    )
    primary = AsyncMock(side_effect=rate_limit)

    with patch.object(embeddings_module, "aembedding", primary):
        result = await embeddings_module.embed(["hello"])

    assert len(result) == 1
    assert isinstance(result[0], np.ndarray)
    primary.assert_awaited_once()
    fallback_called.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_uses_openai_directly_when_key_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        embeddings_module.settings,
        "openai_api_key",
        SecretStr("sk-good"),
        raising=False,
    )

    primary = AsyncMock(return_value=_fake_response(dim=3, count=2))
    fallback_called = AsyncMock()
    monkeypatch.setattr(
        embeddings_module,
        "_call_with_token_fallback",
        fallback_called,
    )

    with patch.object(embeddings_module, "aembedding", primary):
        result = await embeddings_module.embed(["a", "b"])

    assert len(result) == 2
    primary.assert_awaited_once()
    fallback_called.assert_not_awaited()

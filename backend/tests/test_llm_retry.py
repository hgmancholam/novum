"""Tests for ``app.llm.retry``."""

from __future__ import annotations

import httpx
import litellm
import pytest

from app.llm.retry import RETRYABLE_EXCEPTIONS, create_retry_decorator, retry_llm


def test_retryable_exceptions_includes_transient_http_errors() -> None:
    assert httpx.TimeoutException in RETRYABLE_EXCEPTIONS
    assert httpx.ConnectError in RETRYABLE_EXCEPTIONS
    assert httpx.HTTPStatusError in RETRYABLE_EXCEPTIONS


def test_retryable_exceptions_includes_rate_limit_error() -> None:
    """GitHub Models enforces per-model per-minute quotas; rotating across
    the model pool requires tenacity to retry on RateLimitError."""
    assert litellm.RateLimitError in RETRYABLE_EXCEPTIONS


@pytest.mark.asyncio
async def test_retries_on_timeout_then_succeeds() -> None:
    calls = {"n": 0}

    @retry_llm
    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.TimeoutException("boom")
        return "ok"

    result = await flaky()
    assert result == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_gives_up_after_five_attempts() -> None:
    """Default ``retry_llm`` is sized for GitHub Models' 60 s rate-limit
    window: 5 attempts with 1->60 s exponential backoff."""
    calls = {"n": 0}

    @retry_llm
    async def always_fails() -> str:
        calls["n"] += 1
        raise httpx.TimeoutException("nope")

    with pytest.raises(httpx.TimeoutException):
        await always_fails()
    assert calls["n"] == 5


@pytest.mark.asyncio
async def test_does_not_retry_on_non_retryable_error() -> None:
    calls = {"n": 0}

    @retry_llm
    async def bad_value() -> str:
        calls["n"] += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        await bad_value()
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_create_retry_decorator_respects_max_attempts() -> None:
    decorator = create_retry_decorator(max_attempts=5)
    calls = {"n": 0}

    @decorator
    async def always_fails() -> str:
        calls["n"] += 1
        raise httpx.ConnectError("down")

    with pytest.raises(httpx.ConnectError):
        await always_fails()
    assert calls["n"] == 5

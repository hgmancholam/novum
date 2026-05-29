"""Unit tests for ``app.health.probes`` (IP-27 §3 Task 3.1)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from app.health import probes as probes_module
from app.health.probes import (
    AuthError,
    DisabledError,
    NoKeyError,
    RateLimitError,
    UnreachableError,
    UpstreamError,
    _make_disabled_runner,
    _raise_mapped,
)


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _FakeHTTPError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"http {code}")
        self.response = _FakeResponse(code)


class _FakeConnectError(Exception):
    """Mimics ``httpx.ConnectError`` for the name-based mapping branch."""


# ---------------------------------------------------------------------------
# Mapping helper.
# ---------------------------------------------------------------------------


async def _expect_raises(
    runner: Callable[[], Awaitable[None]],
    exc_type: type[Exception],
) -> Exception:
    with pytest.raises(exc_type) as info:
        await runner()
    return info.value  # type: ignore[return-value]


def test_raise_mapped_auth_401() -> None:
    with pytest.raises(AuthError):
        _raise_mapped(_FakeHTTPError(401))


def test_raise_mapped_auth_403() -> None:
    with pytest.raises(AuthError):
        _raise_mapped(_FakeHTTPError(403))


def test_raise_mapped_rate_limit_429() -> None:
    with pytest.raises(RateLimitError):
        _raise_mapped(_FakeHTTPError(429))


def test_raise_mapped_upstream_5xx() -> None:
    with pytest.raises(UpstreamError) as info:
        _raise_mapped(_FakeHTTPError(503))
    assert "503" in str(info.value)


def test_raise_mapped_unreachable_by_name() -> None:
    with pytest.raises(UnreachableError):
        _raise_mapped(_FakeConnectError("dns failed"))


def test_raise_mapped_unknown_falls_back_to_upstream() -> None:
    with pytest.raises(UpstreamError) as info:
        _raise_mapped(ValueError("???"))
    assert "unknown" in str(info.value)


# ---------------------------------------------------------------------------
# Anthropic runner: env-var presence (AC-04).
# ---------------------------------------------------------------------------


async def test_anthropic_runner_no_key_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.health.probes import _anthropic_runner

    monkeypatch.setattr(probes_module.settings, "anthropic_api_key", None)
    err = await _expect_raises(_anthropic_runner, NoKeyError)
    assert err.var_name == "ANTHROPIC_API_KEY"


async def test_anthropic_runner_no_key_when_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import SecretStr

    from app.health.probes import _anthropic_runner

    monkeypatch.setattr(probes_module.settings, "anthropic_api_key", SecretStr("   "))
    with pytest.raises(NoKeyError):
        await _anthropic_runner()


async def test_anthropic_runner_succeeds_when_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import SecretStr

    from app.health.probes import _anthropic_runner

    monkeypatch.setattr(
        probes_module.settings, "anthropic_api_key", SecretStr("sk-ant-fake")
    )
    # Must not raise and must not perform any network call (no LLM patch needed).
    await _anthropic_runner()


# ---------------------------------------------------------------------------
# Disabled runners (OpenAI / Gemini / GitHub Models).
# ---------------------------------------------------------------------------


async def test_disabled_runner_raises_disabled_error() -> None:
    runner = _make_disabled_runner("not enabled in V1")
    err = await _expect_raises(runner, DisabledError)
    assert "not enabled in V1" in str(err)


# ---------------------------------------------------------------------------
# Source-backed runner: NoKey when registry has gated the source out.
# ---------------------------------------------------------------------------


async def test_source_runner_no_key_when_source_unregistered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.enums import SourceType
    from app.health.probes import _make_source_runner

    class _Reg:
        def types(self) -> list[SourceType]:
            return []  # Tavily intentionally absent.

    monkeypatch.setattr(probes_module, "get_source_registry", lambda: _Reg())
    runner = _make_source_runner(SourceType.TAVILY, "TAVILY_API_KEY")
    err = await _expect_raises(runner, NoKeyError)
    assert err.var_name == "TAVILY_API_KEY"


async def test_source_runner_disabled_when_no_key_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.enums import SourceType
    from app.health.probes import _make_source_runner

    class _Reg:
        def types(self) -> list[SourceType]:
            return []

    monkeypatch.setattr(probes_module, "get_source_registry", lambda: _Reg())
    runner = _make_source_runner(SourceType.WIKIPEDIA, None)
    await _expect_raises(runner, DisabledError)


async def test_source_runner_upstream_error_when_health_check_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.enums import SourceType
    from app.health.probes import _make_source_runner

    class _Source:
        async def health_check(self) -> bool:
            return False

    class _Reg:
        def types(self) -> list[SourceType]:
            return [SourceType.WIKIPEDIA]

        def get(self, _t: SourceType) -> _Source:
            return _Source()

    monkeypatch.setattr(probes_module, "get_source_registry", lambda: _Reg())
    runner = _make_source_runner(SourceType.WIKIPEDIA, None)
    err = await _expect_raises(runner, UpstreamError)
    assert "health_check returned False" in str(err)


async def test_source_runner_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.domain.enums import SourceType
    from app.health.probes import _make_source_runner

    class _Source:
        async def health_check(self) -> bool:
            return True

    class _Reg:
        def types(self) -> list[SourceType]:
            return [SourceType.WIKIPEDIA]

        def get(self, _t: SourceType) -> _Source:
            return _Source()

    monkeypatch.setattr(probes_module, "get_source_registry", lambda: _Reg())
    runner = _make_source_runner(SourceType.WIKIPEDIA, None)
    await runner()  # must not raise


async def test_source_runner_propagates_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.enums import SourceType
    from app.health.probes import _make_source_runner

    class _Source:
        async def health_check(self) -> bool:
            raise asyncio.TimeoutError

    class _Reg:
        def types(self) -> list[SourceType]:
            return [SourceType.WIKIPEDIA]

        def get(self, _t: SourceType) -> _Source:
            return _Source()

    monkeypatch.setattr(probes_module, "get_source_registry", lambda: _Reg())
    runner = _make_source_runner(SourceType.WIKIPEDIA, None)
    with pytest.raises(asyncio.TimeoutError):
        await runner()


async def test_source_runner_maps_auth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.enums import SourceType
    from app.health.probes import _make_source_runner

    class _Source:
        async def health_check(self) -> bool:
            raise _FakeHTTPError(401)

    class _Reg:
        def types(self) -> list[SourceType]:
            return [SourceType.WIKIPEDIA]

        def get(self, _t: SourceType) -> _Source:
            return _Source()

    monkeypatch.setattr(probes_module, "get_source_registry", lambda: _Reg())
    runner = _make_source_runner(SourceType.WIKIPEDIA, None)
    with pytest.raises(AuthError):
        await runner()


# ---------------------------------------------------------------------------
# PROBES registry shape.
# ---------------------------------------------------------------------------


def test_probes_registry_contains_v1_services() -> None:
    ids = {spec.id for spec in probes_module.PROBES}
    assert {
        "anthropic",
        "openai",
        "gemini",
        "github_models",
        "tavily",
        "wikipedia",
        "semantic_scholar",
        "openalex",
        "postgres",
    } <= ids

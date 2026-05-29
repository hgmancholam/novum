"""Unit tests for ``app.health.registry`` (IP-27 §3 Task 3.2)."""

from __future__ import annotations

import asyncio

import pytest

from app.health import registry as registry_module
from app.health.probes import (
    AuthError,
    DisabledError,
    NoKeyError,
    ProbeSpec,
    RateLimitError,
    UnreachableError,
    UpstreamError,
)
from app.health.models import ServiceCategory, ServiceStatus
from app.health.registry import HealthRegistry

pytestmark = pytest.mark.asyncio


def _spec(runner, *, id: str = "svc", name: str = "Svc") -> ProbeSpec:
    return ProbeSpec(id=id, name=name, category=ServiceCategory.LLM, runner=runner)


async def _ok_runner() -> None:
    return None


# ---------------------------------------------------------------------------
# Status mapping (BRD-27 §4.8 table).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc,expected_status,expected_msg_substr",
    [
        (asyncio.TimeoutError(), ServiceStatus.DOWN, "probe timeout"),
        (DisabledError("not enabled in V1"), ServiceStatus.DISABLED, "not enabled"),
        (NoKeyError("ANTHROPIC_API_KEY"), ServiceStatus.NO_KEY, "ANTHROPIC_API_KEY"),
        (AuthError("authentication failed"), ServiceStatus.DOWN, "authentication"),
        (RateLimitError("rate limited"), ServiceStatus.DEGRADED, "rate limited"),
        (UnreachableError("unreachable"), ServiceStatus.DOWN, "unreachable"),
        (UpstreamError(503), ServiceStatus.DOWN, "503"),
        (RuntimeError("???"), ServiceStatus.DOWN, "internal probe error"),
    ],
)
async def test_status_mapping(exc, expected_status, expected_msg_substr) -> None:
    async def _raises() -> None:
        raise exc

    reg = HealthRegistry(probes=(_spec(_raises),))
    snap = await reg.snapshot()
    [svc] = snap.services
    assert svc.status is expected_status
    assert svc.message is not None
    assert expected_msg_substr.lower() in svc.message.lower()


async def test_ok_marks_latency_and_status_ok() -> None:
    reg = HealthRegistry(probes=(_spec(_ok_runner),))
    snap = await reg.snapshot()
    [svc] = snap.services
    assert svc.status is ServiceStatus.OK
    assert svc.message is None
    assert svc.latency_ms is not None and svc.latency_ms >= 0


async def test_degraded_when_latency_above_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reg = HealthRegistry(probes=(_spec(_ok_runner),))
    reg.LATENCY_DEGRADED_MS = -1  # everything is "too slow"
    snap = await reg.snapshot()
    [svc] = snap.services
    assert svc.status is ServiceStatus.DEGRADED
    assert svc.message is not None and "high latency" in svc.message


async def test_timeout_when_runner_hangs() -> None:
    async def _hang() -> None:
        await asyncio.sleep(10)

    reg = HealthRegistry(probes=(_spec(_hang),))
    reg.PROBE_TIMEOUT_S = 0.05
    snap = await reg.snapshot()
    [svc] = snap.services
    assert svc.status is ServiceStatus.DOWN
    assert svc.message == "probe timeout"


# ---------------------------------------------------------------------------
# Cache TTL.
# ---------------------------------------------------------------------------


async def test_cache_hit_within_ttl() -> None:
    calls = 0

    async def _counted() -> None:
        nonlocal calls
        calls += 1

    reg = HealthRegistry(probes=(_spec(_counted),))
    first = await reg.snapshot()
    second = await reg.snapshot()
    assert calls == 1
    assert first.checked_at == second.checked_at
    assert first.cached is False
    assert second.cached is True


async def test_refresh_bypasses_cache() -> None:
    calls = 0

    async def _counted() -> None:
        nonlocal calls
        calls += 1

    reg = HealthRegistry(probes=(_spec(_counted),))
    await reg.snapshot()
    snap = await reg.refresh()
    assert calls == 2
    assert snap.cached is False


async def test_cache_expires_after_ttl() -> None:
    calls = 0

    async def _counted() -> None:
        nonlocal calls
        calls += 1

    reg = HealthRegistry(probes=(_spec(_counted),))
    reg.CACHE_TTL_S = 0.0  # always stale
    await reg.snapshot()
    await reg.snapshot()
    assert calls == 2


# ---------------------------------------------------------------------------
# Single-flight (AC-02).
# ---------------------------------------------------------------------------


async def test_single_flight_coalesces_concurrent_requests() -> None:
    calls = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def _slow() -> None:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()

    reg = HealthRegistry(probes=(_spec(_slow),))

    # Fan out 50 concurrent snapshot() requests.
    tasks = [asyncio.create_task(reg.snapshot()) for _ in range(50)]

    # Wait until the runner has started exactly once.
    await started.wait()
    release.set()

    results = await asyncio.gather(*tasks)
    assert calls == 1
    assert all(r.checked_at == results[0].checked_at for r in results)
    cached_count = sum(1 for r in results if r.cached)
    # Exactly one initiator gets cached=False; the rest get cached=True.
    assert cached_count == 49


async def test_get_registry_returns_singleton() -> None:
    registry_module.reset_registry()
    a = registry_module.get_registry()
    b = registry_module.get_registry()
    assert a is b
    registry_module.reset_registry()

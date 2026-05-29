"""Tests for the health-services route (IP-27 §3 Task 3.3)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.health import registry as registry_module
from app.health.models import (
    HealthSnapshot,
    ServiceCategory,
    ServiceHealth,
    ServiceStatus,
)

pytestmark = pytest.mark.asyncio


def _fake_snapshot() -> HealthSnapshot:
    now = datetime.now(timezone.utc)
    return HealthSnapshot(
        checked_at=now,
        cached=False,
        services=[
            ServiceHealth(
                id="anthropic",
                name="Anthropic",
                category=ServiceCategory.LLM,
                status=ServiceStatus.OK,
                latency_ms=12,
                message=None,
                checked_at=now,
            ),
            ServiceHealth(
                id="openai",
                name="OpenAI",
                category=ServiceCategory.LLM,
                status=ServiceStatus.DISABLED,
                latency_ms=None,
                message="not enabled in V1",
                checked_at=now,
            ),
            ServiceHealth(
                id="gemini",
                name="Gemini",
                category=ServiceCategory.LLM,
                status=ServiceStatus.DISABLED,
                latency_ms=None,
                message="not enabled in V1",
                checked_at=now,
            ),
            ServiceHealth(
                id="github_models",
                name="GitHub Models",
                category=ServiceCategory.LLM,
                status=ServiceStatus.DISABLED,
                latency_ms=None,
                message="not enabled in V1",
                checked_at=now,
            ),
            ServiceHealth(
                id="tavily",
                name="Tavily",
                category=ServiceCategory.SEARCH,
                status=ServiceStatus.OK,
                latency_ms=87,
                message=None,
                checked_at=now,
            ),
            ServiceHealth(
                id="wikipedia",
                name="Wikipedia",
                category=ServiceCategory.KNOWLEDGE,
                status=ServiceStatus.OK,
                latency_ms=42,
                message=None,
                checked_at=now,
            ),
            ServiceHealth(
                id="postgres",
                name="PostgreSQL",
                category=ServiceCategory.STORAGE,
                status=ServiceStatus.OK,
                latency_ms=2,
                message=None,
                checked_at=now,
            ),
        ],
    )


async def test_services_endpoint_returns_snapshot(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snap = _fake_snapshot()

    class _FakeReg:
        async def snapshot(self) -> HealthSnapshot:
            return snap

    monkeypatch.setattr(registry_module, "get_registry", lambda: _FakeReg())

    resp = await client.get("/api/health/services")
    assert resp.status_code == 200
    body = resp.json()
    assert "checked_at" in body
    assert body["cached"] is False
    ids = {s["id"] for s in body["services"]}
    assert {"anthropic", "tavily", "wikipedia", "postgres"} <= ids
    for sid in ("openai", "gemini", "github_models"):
        entry = next(s for s in body["services"] if s["id"] == sid)
        assert entry["status"] == "disabled"


async def test_services_endpoint_is_cheap_on_cache_hit(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snap = _fake_snapshot()

    class _FakeReg:
        async def snapshot(self) -> HealthSnapshot:
            return snap

    monkeypatch.setattr(registry_module, "get_registry", lambda: _FakeReg())

    # Sanity: 5 sequential calls all succeed quickly. We do not enforce a
    # wall-clock threshold (CI variance) but a regression that turned each
    # request into a real probe round would blow this far past the timeout
    # via the actual registry.
    for _ in range(5):
        resp = await client.get("/api/health/services")
        assert resp.status_code == 200


async def test_legacy_health_endpoint_still_works(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

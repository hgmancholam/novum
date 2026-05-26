"""Integration tests for run routes (BRD-03 §4.7)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event

pytestmark = pytest.mark.asyncio


_VALID_BODY = {
    "question": "What is the capital of France?",
    "user_context": None,
    "output_format": "prose",
    "confidence_threshold": 0.7,
}


# ---------------------------------------------------------------------------
# Health (sanity: router is mounted)
# ---------------------------------------------------------------------------


async def test_health_via_router(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# AC-01 — create run
# ---------------------------------------------------------------------------


async def test_create_run_returns_201_and_persists(
    client: AsyncClient, seeded_user: str
) -> None:
    response = await client.post(
        "/api/runs",
        json=_VALID_BODY,
        headers={"X-Username": seeded_user},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["owner_username"] == seeded_user
    assert data["stop_reason"] is None


# ---------------------------------------------------------------------------
# AC-02 — list runs
# ---------------------------------------------------------------------------


async def test_list_runs_orders_desc_by_started_at(
    client: AsyncClient, seeded_user: str
) -> None:
    for _ in range(3):
        r = await client.post(
            "/api/runs", json=_VALID_BODY, headers={"X-Username": seeded_user}
        )
        assert r.status_code == 201

    response = await client.get(
        "/api/runs", headers={"X-Username": seeded_user}
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 3
    timestamps = [item["started_at"] for item in items]
    assert timestamps == sorted(timestamps, reverse=True)


# ---------------------------------------------------------------------------
# AC-03 — fork
# ---------------------------------------------------------------------------


async def test_fork_run_sets_parent_and_event(
    client: AsyncClient,
    sqlite_session: AsyncSession,
    seeded_user: str,
) -> None:
    create = await client.post(
        "/api/runs", json=_VALID_BODY, headers={"X-Username": seeded_user}
    )
    run_id = create.json()["id"]

    event = Event(
        run_id=uuid.UUID(run_id),
        step_index=1,
        type="PlanCreated",
        payload={"sub_claims": [], "rationale": "r"},
    )
    sqlite_session.add(event)
    await sqlite_session.commit()
    event_id = str(event.id)

    response = await client.post(
        f"/api/runs/{run_id}/fork",
        json={"event_id": event_id},
        headers={"X-Username": seeded_user},
    )
    assert response.status_code == 201
    forked = response.json()
    assert forked["parent_run_id"] == run_id
    assert forked["forked_at_event_id"] == event_id


# ---------------------------------------------------------------------------
# Auth & errors
# ---------------------------------------------------------------------------


async def test_missing_username_returns_401(client: AsyncClient) -> None:
    response = await client.post("/api/runs", json=_VALID_BODY)
    assert response.status_code == 401


async def test_list_missing_username_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/runs")
    assert response.status_code == 401


async def test_get_run_does_not_require_username(
    client: AsyncClient, seeded_user: str
) -> None:
    """RF-05: runs are public-by-URL — GET /api/runs/{id} is unauthenticated."""
    create = await client.post(
        "/api/runs", json=_VALID_BODY, headers={"X-Username": seeded_user}
    )
    run_id = create.json()["id"]

    response = await client.get(f"/api/runs/{run_id}")  # no header
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_unknown_run_returns_404(
    client: AsyncClient, seeded_user: str
) -> None:
    response = await client.get(f"/api/runs/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_cancel_unknown_run_returns_404(
    client: AsyncClient, seeded_user: str
) -> None:
    response = await client.post(
        f"/api/runs/{uuid.uuid4()}/cancel",
        headers={"X-Username": seeded_user},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# AC-04 — cancel via HTTP
# ---------------------------------------------------------------------------


async def test_cancel_endpoint_sets_user_cancelled(
    client: AsyncClient, seeded_user: str
) -> None:
    create = await client.post(
        "/api/runs", json=_VALID_BODY, headers={"X-Username": seeded_user}
    )
    run_id = create.json()["id"]

    response = await client.post(
        f"/api/runs/{run_id}/cancel", headers={"X-Username": seeded_user}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stop_reason"] == "user_cancelled"
    assert data["stopped_at"] is not None


# ---------------------------------------------------------------------------
# AC-05 — resume via HTTP
# ---------------------------------------------------------------------------


async def test_resume_endpoint_clears_stop_state(
    client: AsyncClient, seeded_user: str
) -> None:
    create = await client.post(
        "/api/runs", json=_VALID_BODY, headers={"X-Username": seeded_user}
    )
    run_id = create.json()["id"]
    await client.post(
        f"/api/runs/{run_id}/cancel", headers={"X-Username": seeded_user}
    )

    response = await client.post(
        f"/api/runs/{run_id}/resume", headers={"X-Username": seeded_user}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stop_reason"] is None
    assert data["stopped_at"] is None


# ---------------------------------------------------------------------------
# Events placeholder — 501 (BRD-10 future work)
# ---------------------------------------------------------------------------


async def test_events_placeholder_returns_501(
    client: AsyncClient, seeded_user: str
) -> None:
    create = await client.post(
        "/api/runs", json=_VALID_BODY, headers={"X-Username": seeded_user}
    )
    run_id = create.json()["id"]

    response = await client.get(f"/api/runs/{run_id}/events")
    assert response.status_code == 501
    assert "BRD-10" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Routing sanity: /health is registered exactly once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_route_registered_exactly_once() -> None:
    from app.main import app as fastapi_app

    health_paths = [
        r for r in fastapi_app.routes if getattr(r, "path", None) == "/health"
    ]
    assert len(health_paths) == 1

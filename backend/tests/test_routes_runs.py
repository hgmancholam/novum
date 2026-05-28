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
    client: AsyncClient, seeded_user: str, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/runs",
        json=_VALID_BODY,
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["owner_username"] == seeded_user
    assert data["stop_reason"] is None


# ---------------------------------------------------------------------------
# AC-02 — list runs (BRD-20 keyset)
# ---------------------------------------------------------------------------


async def test_list_runs_returns_envelope_shape(
    client: AsyncClient, seeded_user: str, auth_headers: dict[str, str]
) -> None:
    """BRD-20 AC-07: response is {items, has_more, next_cursor}."""
    for _ in range(3):
        r = await client.post(
            "/api/runs", json=_VALID_BODY, headers=auth_headers
        )
        assert r.status_code == 201

    response = await client.get("/api/runs", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) >= {"items", "has_more", "next_cursor"}
    assert isinstance(body["items"], list)
    assert len(body["items"]) == 3
    timestamps = [item["started_at"] for item in body["items"]]
    assert timestamps == sorted(timestamps, reverse=True)
    assert all(item["username"] == seeded_user for item in body["items"])
    assert body["has_more"] is False
    assert body["next_cursor"] is None


async def test_list_runs_paginates_with_cursor(
    client: AsyncClient, seeded_user: str, auth_headers: dict[str, str]
) -> None:
    """BRD-20 AC-08: cursor pages traverse the full list without overlap."""
    for _ in range(5):
        await client.post("/api/runs", json=_VALID_BODY, headers=auth_headers)

    page1 = (
        await client.get("/api/runs?limit=2", headers=auth_headers)
    ).json()
    assert page1["has_more"] is True
    assert page1["next_cursor"]
    page2 = (
        await client.get(
            f"/api/runs?limit=2&cursor={page1['next_cursor']}",
            headers=auth_headers,
        )
    ).json()
    ids1 = {i["id"] for i in page1["items"]}
    ids2 = {i["id"] for i in page2["items"]}
    assert ids1.isdisjoint(ids2)


async def test_list_runs_invalid_cursor_returns_400(
    client: AsyncClient, seeded_user: str, auth_headers: dict[str, str]
) -> None:
    """BRD-20 AC-11: malformed cursor → 400 with literal 'Invalid cursor'."""
    response = await client.get(
        "/api/runs?cursor=%21%21%21not-base64", headers=auth_headers
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid cursor"


async def test_list_runs_includes_all_users(
    client: AsyncClient,
    sqlite_session: AsyncSession,
    seeded_user: str,
    auth_headers: dict[str, str],
) -> None:
    """History is shared across users (RF-05 public-by-URL)."""
    from app.models import User
    from app.services.auth_service import AuthService

    auth = AuthService(sqlite_session)
    _, bob_token = await auth.register("bob")
    headers2 = {"X-Username": "bob", "X-Token": bob_token}

    await client.post("/api/runs", json=_VALID_BODY, headers=headers2)
    await client.post("/api/runs", json=_VALID_BODY, headers=auth_headers)

    body = (await client.get("/api/runs", headers=auth_headers)).json()
    usernames = {item["username"] for item in body["items"]}
    assert {seeded_user, "bob"} <= usernames
    _ = User  # silence unused-import lint


# ---------------------------------------------------------------------------
# AC-03 — fork
# ---------------------------------------------------------------------------


async def test_fork_run_sets_parent_and_event(
    client: AsyncClient,
    sqlite_session: AsyncSession,
    seeded_user: str,
    auth_headers: dict[str, str],
) -> None:
    create = await client.post(
        "/api/runs", json=_VALID_BODY, headers=auth_headers
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
        headers=auth_headers,
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
    client: AsyncClient, seeded_user: str, auth_headers: dict[str, str]
) -> None:
    """RF-05: runs are public-by-URL — GET /api/runs/{id} is unauthenticated."""
    create = await client.post(
        "/api/runs", json=_VALID_BODY, headers=auth_headers
    )
    run_id = create.json()["id"]

    response = await client.get(f"/api/runs/{run_id}")  # no header
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_unknown_run_returns_404(
    client: AsyncClient, seeded_user: str, auth_headers: dict[str, str]
) -> None:
    response = await client.get(f"/api/runs/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_cancel_unknown_run_returns_404(
    client: AsyncClient, seeded_user: str, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"/api/runs/{uuid.uuid4()}/cancel",
        headers=auth_headers,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# AC-04 — cancel via HTTP
# ---------------------------------------------------------------------------


async def test_cancel_endpoint_sets_user_cancelled(
    client: AsyncClient, seeded_user: str, auth_headers: dict[str, str]
) -> None:
    create = await client.post(
        "/api/runs", json=_VALID_BODY, headers=auth_headers
    )
    run_id = create.json()["id"]

    response = await client.post(
        f"/api/runs/{run_id}/cancel", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stop_reason"] == "user_cancelled"
    assert data["stopped_at"] is not None


# ---------------------------------------------------------------------------
# AC-05 — resume via HTTP
# ---------------------------------------------------------------------------


async def test_resume_endpoint_clears_stop_state(
    client: AsyncClient,
    sqlite_session: AsyncSession,
    seeded_user: str,
    auth_headers: dict[str, str],
) -> None:
    create = await client.post(
        "/api/runs", json=_VALID_BODY, headers=auth_headers
    )
    run_id = create.json()["id"]
    await client.post(
        f"/api/runs/{run_id}/cancel", headers=auth_headers
    )
    # IP-15: resume requires an anchor `Stopped(user_cancelled)` event.
    sqlite_session.add(
        Event(
            run_id=uuid.UUID(run_id),
            step_index=1,
            type="Stopped",
            payload={"stop_reason": "user_cancelled"},
        )
    )
    await sqlite_session.commit()

    response = await client.post(
        f"/api/runs/{run_id}/resume", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stop_reason"] is None
    assert data["stopped_at"] is None


async def test_resume_endpoint_appends_resume_event(
    client: AsyncClient,
    sqlite_session: AsyncSession,
    seeded_user: str,
    auth_headers: dict[str, str],
) -> None:
    """IP-15 B6: resume appends a ResumedAfterCancel event with parent + payload."""
    import sqlalchemy as sa

    create = await client.post(
        "/api/runs", json=_VALID_BODY, headers=auth_headers
    )
    run_id = create.json()["id"]
    await client.post(
        f"/api/runs/{run_id}/cancel", headers=auth_headers
    )
    anchor = Event(
        run_id=uuid.UUID(run_id),
        step_index=3,
        type="Stopped",
        payload={"stop_reason": "user_cancelled"},
    )
    sqlite_session.add(anchor)
    await sqlite_session.commit()
    await sqlite_session.refresh(anchor)

    response = await client.post(
        f"/api/runs/{run_id}/resume", headers=auth_headers
    )
    assert response.status_code == 200

    query = (
        sa.select(Event)
        .where(Event.run_id == uuid.UUID(run_id))
        .order_by(Event.step_index.desc())
        .limit(1)
    )
    result = await sqlite_session.execute(query)
    latest = result.scalar_one()
    assert latest.type == "ResumedAfterCancel"
    assert latest.parent_event_id == anchor.id
    assert latest.step_index == 4
    assert latest.payload["cancel_event_id"] == str(anchor.id)
    assert latest.payload["resume_point"] == "after_step_3"


async def test_fork_endpoint_rejects_cross_run_event(
    client: AsyncClient,
    sqlite_session: AsyncSession,
    seeded_user: str,
    auth_headers: dict[str, str],
) -> None:
    """IP-15 B2: forking with an event that belongs to a different run → 404."""
    create_a = await client.post(
        "/api/runs", json=_VALID_BODY, headers=auth_headers
    )
    create_b = await client.post(
        "/api/runs", json=_VALID_BODY, headers=auth_headers
    )
    run_a = create_a.json()["id"]
    run_b = create_b.json()["id"]

    event_b = Event(
        run_id=uuid.UUID(run_b),
        step_index=1,
        type="PlanCreated",
        payload={"sub_claims": [], "rationale": "r"},
    )
    sqlite_session.add(event_b)
    await sqlite_session.commit()

    response = await client.post(
        f"/api/runs/{run_a}/fork",
        json={"event_id": str(event_b.id)},
        headers=auth_headers,
    )
    assert response.status_code == 404


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


# ---------------------------------------------------------------------------
# Agent runner wiring at the route layer (BRD-19 / IP-19 §6.1 — T10)
# ---------------------------------------------------------------------------


class _RouteRecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def start(self, run_id) -> None:
        self.calls.append(("start", run_id))

    def cancel(self, run_id) -> bool:
        self.calls.append(("cancel", run_id))
        return True

    async def await_terminal(self, run_id, timeout: float = 5.0) -> None:
        self.calls.append(("await_terminal", run_id))

    async def shutdown(self) -> None:
        self.calls.append(("shutdown", None))

    def is_running(self, run_id) -> bool:
        return False


@pytest.mark.real_agent_runner
async def test_post_runs_invokes_runner_start(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _RouteRecordingRunner()
    monkeypatch.setattr("app.agent.runner.agent_runner", fake)

    response = await client.post(
        "/api/runs",
        json={
            "question": "What is the capital of France?",
            "output_format": "prose",
            "confidence_threshold": 0.7,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    run_id = response.json()["id"]
    assert ("start", __import__("uuid").UUID(run_id)) in fake.calls


@pytest.mark.real_agent_runner
async def test_post_cancel_invokes_runner_cancel(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _RouteRecordingRunner()
    monkeypatch.setattr("app.agent.runner.agent_runner", fake)

    create = await client.post(
        "/api/runs",
        json={"question": "What is the capital of France?", "output_format": "prose", "confidence_threshold": 0.7},
        headers=auth_headers,
    )
    run_id = create.json()["id"]
    fake.calls.clear()

    response = await client.post(f"/api/runs/{run_id}/cancel", headers=auth_headers)

    assert response.status_code == 200
    kinds = [c[0] for c in fake.calls]
    assert "cancel" in kinds


@pytest.mark.real_agent_runner
async def test_post_resume_awaits_terminal_then_starts(
    client: AsyncClient,
    sqlite_session: AsyncSession,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.enums import StopReason
    from app.models import Run

    fake = _RouteRecordingRunner()
    monkeypatch.setattr("app.agent.runner.agent_runner", fake)

    create = await client.post(
        "/api/runs",
        json={"question": "What is the capital of France?", "output_format": "prose", "confidence_threshold": 0.7},
        headers=auth_headers,
    )
    run_id = create.json()["id"]

    # Mark errored with an anchor event so resume can locate it.
    import uuid as _uuid

    run = await sqlite_session.get(Run, _uuid.UUID(run_id))
    assert run is not None
    run.stop_reason = StopReason.ERRORED.value
    sqlite_session.add(
        Event(
            run_id=run.id,
            step_index=1,
            type="AgentErrored",
            payload={
                "error_type": "LLMError",
                "error_message": "boom",
                "recoverable": True,
            },
        )
    )
    await sqlite_session.commit()
    fake.calls.clear()

    response = await client.post(f"/api/runs/{run_id}/resume", headers=auth_headers)

    assert response.status_code == 200
    kinds = [c[0] for c in fake.calls]
    assert kinds[0] == "await_terminal"
    assert kinds[-1] == "start"


# ---------------------------------------------------------------------------
# BRD-20 — DELETE /api/runs/{id}
# ---------------------------------------------------------------------------


async def _create_and_stop(
    client: AsyncClient,
    sqlite_session: AsyncSession,
    auth_headers: dict[str, str],
) -> str:
    """Create a run via API then mark it terminal."""
    from app.domain.enums import StopReason
    from app.models import Run

    create = await client.post(
        "/api/runs", json=_VALID_BODY, headers=auth_headers
    )
    run_id = create.json()["id"]
    run = await sqlite_session.get(Run, uuid.UUID(run_id))
    assert run is not None
    run.stop_reason = StopReason.JUDGE_CONFIRMED.value
    await sqlite_session.commit()
    return run_id


async def test_delete_run_returns_204(
    client: AsyncClient,
    sqlite_session: AsyncSession,
    seeded_user: str,
    auth_headers: dict[str, str],
) -> None:
    """BRD-20 AC-03: finished + owned run yields 204 No Content."""
    run_id = await _create_and_stop(client, sqlite_session, auth_headers)
    response = await client.delete(f"/api/runs/{run_id}", headers=auth_headers)
    assert response.status_code == 204
    assert response.content == b""


async def test_delete_run_missing_auth_returns_401(
    client: AsyncClient,
    sqlite_session: AsyncSession,
    seeded_user: str,
    auth_headers: dict[str, str],
) -> None:
    run_id = await _create_and_stop(client, sqlite_session, auth_headers)
    response = await client.delete(f"/api/runs/{run_id}")
    assert response.status_code == 401


async def test_delete_run_unknown_returns_404_with_literal_detail(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """BRD-20 §14.3: literal detail body is `Run not found: <id>`."""
    rid = uuid.uuid4()
    response = await client.delete(f"/api/runs/{rid}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == f"Run not found: {rid}"


async def test_delete_run_not_owned_returns_403_with_literal_detail(
    client: AsyncClient,
    sqlite_session: AsyncSession,
    seeded_user: str,
    auth_headers: dict[str, str],
) -> None:
    """BRD-20 AC-05, §14.3: foreign run yields 403 with literal detail."""
    from app.services.auth_service import AuthService

    auth = AuthService(sqlite_session)
    _, bob_token = await auth.register("bob")
    headers_bob = {"X-Username": "bob", "X-Token": bob_token}

    run_id = await _create_and_stop(client, sqlite_session, headers_bob)
    response = await client.delete(f"/api/runs/{run_id}", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Run is not owned by the current user."


async def test_delete_run_in_progress_returns_409_with_literal_detail(
    client: AsyncClient,
    seeded_user: str,
    auth_headers: dict[str, str],
) -> None:
    """BRD-20 AC-04, §14.3: in-flight run yields 409 with literal detail."""
    create = await client.post(
        "/api/runs", json=_VALID_BODY, headers=auth_headers
    )
    run_id = create.json()["id"]
    response = await client.delete(f"/api/runs/{run_id}", headers=auth_headers)
    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "Cannot delete a run that is still in progress. Cancel it first."
    )


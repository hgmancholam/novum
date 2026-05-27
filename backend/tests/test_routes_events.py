"""Integration tests for ``GET /api/runs/{run_id}/events`` (IP-10 §4.5).

These tests run the SSE route end-to-end through an ASGI client. To keep the
suite fast, ``POLL_INTERVAL_S`` is patched to 0 via ``monkeypatch`` so the
generator only sleeps between polls when explicitly needed.

We seed at least one ``Stopped`` event so the generator terminates and the
response body is fully drained.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, Run
from app.sse.manager import connection_manager

pytestmark = pytest.mark.asyncio


async def _seed_stopped_run(session: AsyncSession) -> UUID:
    run = Run(
        owner_username="testuser",
        question="What is the meaning of life?",
        output_format="prose",
        confidence_threshold=0.7,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    session.add(
        Event(
            run_id=run.id,
            step_index=1,
            type="ToolCalled",
            payload={"source_type": "tavily", "query": "q", "query_intent": "i"},
        )
    )
    session.add(
        Event(
            run_id=run.id,
            step_index=2,
            type="EvidenceAdded",
            payload={"claim_id": "c1", "summary": "s", "url": "u"},
        )
    )
    session.add(
        Event(
            run_id=run.id,
            step_index=3,
            type="Stopped",
            payload={"stop_reason": "judge_confirmed", "final_confidence": 0.9},
        )
    )
    await session.commit()
    return run.id


def _parse_sse(body: str) -> list[dict[str, str]]:
    """Parse the SSE body into a list of ``{event, data, id}`` dicts."""
    frames: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in body.splitlines():
        if line == "":
            if current:
                frames.append(current)
                current = {}
            continue
        if line.startswith(":"):
            # Comment / keepalive — ignore.
            continue
        key, _, value = line.partition(":")
        # SSE allows a single leading space after the colon.
        if value.startswith(" "):
            value = value[1:]
        current[key] = value
    if current:
        frames.append(current)
    return frames


@pytest.fixture(autouse=True)
def _fast_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the stream non-blocking under tests."""
    monkeypatch.setattr("app.sse.stream.POLL_INTERVAL_S", 0.0)
    monkeypatch.setattr("app.sse.stream.HEARTBEAT_TICKS", 10_000)


@pytest.fixture(autouse=True)
def _reset_manager() -> None:
    connection_manager.reset()


async def test_stream_returns_event_stream_content_type(
    client: AsyncClient, sqlite_session: AsyncSession
) -> None:
    run_id = await _seed_stopped_run(sqlite_session)
    resp = await client.get(f"/api/runs/{run_id}/events")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["connection"] == "keep-alive"


async def test_stream_delivers_all_events_in_order(
    client: AsyncClient, sqlite_session: AsyncSession
) -> None:
    run_id = await _seed_stopped_run(sqlite_session)
    resp = await client.get(f"/api/runs/{run_id}/events")
    frames = _parse_sse(resp.text)
    types = [f["event"] for f in frames if f.get("event")]
    assert types == ["ToolCalled", "EvidenceAdded", "Stopped"]
    assert [f["id"] for f in frames if f.get("id")] == ["1", "2", "3"]


async def test_resume_via_query_param_skips_seen_events(
    client: AsyncClient, sqlite_session: AsyncSession
) -> None:
    run_id = await _seed_stopped_run(sqlite_session)
    resp = await client.get(
        f"/api/runs/{run_id}/events?last_event_id=1"
    )
    frames = _parse_sse(resp.text)
    types = [f["event"] for f in frames if f.get("event")]
    assert types == ["EvidenceAdded", "Stopped"]


async def test_resume_via_header_fallback(
    client: AsyncClient, sqlite_session: AsyncSession
) -> None:
    run_id = await _seed_stopped_run(sqlite_session)
    resp = await client.get(
        f"/api/runs/{run_id}/events",
        headers={"Last-Event-ID": "2"},
    )
    frames = _parse_sse(resp.text)
    types = [f["event"] for f in frames if f.get("event")]
    assert types == ["Stopped"]


async def test_query_param_wins_over_header(
    client: AsyncClient, sqlite_session: AsyncSession
) -> None:
    run_id = await _seed_stopped_run(sqlite_session)
    resp = await client.get(
        f"/api/runs/{run_id}/events?last_event_id=2",
        headers={"Last-Event-ID": "0"},
    )
    frames = _parse_sse(resp.text)
    types = [f["event"] for f in frames if f.get("event")]
    # If the header had won, we would also receive ToolCalled + EvidenceAdded.
    assert types == ["Stopped"]


async def test_disconnect_cleans_up_manager_state(
    client: AsyncClient, sqlite_session: AsyncSession
) -> None:
    run_id = await _seed_stopped_run(sqlite_session)
    # Fully drain the response so the ``finally`` block in the route runs.
    resp = await client.get(f"/api/runs/{run_id}/events")
    assert resp.status_code == 200
    # After the response is consumed, the manager should have no active conns.
    assert connection_manager.active_connections(run_id) == 0


async def test_cancellation_emits_synthetic_cancelled_frame(
    client: AsyncClient, sqlite_session: AsyncSession
) -> None:
    # A run that has NO ``Stopped`` event in the DB yet — the only way out is
    # the cancellation flag.
    run = Run(
        owner_username="testuser",
        question="Will it cancel?",
        output_format="prose",
        confidence_threshold=0.7,
    )
    sqlite_session.add(run)
    await sqlite_session.commit()
    await sqlite_session.refresh(run)
    sqlite_session.add(
        Event(
            run_id=run.id,
            step_index=1,
            type="ToolCalled",
            payload={"source_type": "tavily", "query": "q", "query_intent": "i"},
        )
    )
    await sqlite_session.commit()

    # Pre-cancel before the request starts so the very first poll sees the flag.
    connection_manager.cancel(run.id)

    resp = await client.get(f"/api/runs/{run.id}/events")
    frames = _parse_sse(resp.text)
    types = [f["event"] for f in frames if f.get("event")]
    assert "cancelled" in types
    # Synthetic frame carries empty JSON object.
    cancelled = next(f for f in frames if f.get("event") == "cancelled")
    assert cancelled["data"] == "{}"


async def test_run_with_no_events_then_cancelled(
    client: AsyncClient, sqlite_session: AsyncSession
) -> None:
    run = Run(
        owner_username="testuser",
        question="Empty run cancel",
        output_format="prose",
        confidence_threshold=0.7,
    )
    sqlite_session.add(run)
    await sqlite_session.commit()
    await sqlite_session.refresh(run)
    connection_manager.cancel(run.id)

    resp = await client.get(f"/api/runs/{run.id}/events")
    frames = _parse_sse(resp.text)
    types = [f["event"] for f in frames if f.get("event")]
    assert types == ["cancelled"]


async def test_event_payload_is_json_serialized(
    client: AsyncClient, sqlite_session: AsyncSession
) -> None:
    import json

    run_id = await _seed_stopped_run(sqlite_session)
    resp = await client.get(f"/api/runs/{run_id}/events")
    frames = _parse_sse(resp.text)
    first_real = next(f for f in frames if f.get("event") == "ToolCalled")
    payload: dict[str, Any] = json.loads(first_real["data"])
    assert payload["step_index"] == 1
    assert payload["type"] == "ToolCalled"
    assert payload["source_type"] == "tavily"

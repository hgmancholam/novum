"""Unit tests for ``app.sse.stream.event_stream`` (IP-10 §4.5).

Uses an in-memory fake ``EventService`` to avoid the DB entirely.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.sse.manager import ConnectionManager
from app.sse.stream import _parse_last_event_id, event_stream


class FakeEventService:
    """Hand-rolled ``EventService`` stand-in.

    ``batches`` is a list of event-batches; each ``get_events`` call pops the
    next batch (filtering by ``after_step``). When the queue is exhausted the
    service returns an empty list forever.
    """

    def __init__(self, batches: list[list[dict[str, Any]]]) -> None:
        self._batches = list(batches)
        self.calls: list[tuple[UUID, int, int]] = []

    async def get_events(
        self,
        run_id: UUID,
        after_step: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self.calls.append((run_id, after_step, limit))
        if not self._batches:
            return []
        batch = self._batches.pop(0)
        filtered = [
            e for e in batch if int(e.get("step_index", 0)) > after_step
        ]
        return filtered[:limit]


def _ev(step: int, event_type: str = "ToolCalled", **payload: Any) -> dict[str, Any]:
    return {
        "id": f"00000000-0000-0000-0000-{step:012d}",
        "run_id": "00000000-0000-0000-0000-000000000000",
        "step_index": step,
        "parent_event_id": None,
        "type": event_type,
        "created_at": "2026-05-26T00:00:00+00:00",
        **payload,
    }


async def _collect(generator: Any, *, max_frames: int = 50) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    async for frame in generator:
        frames.append(frame)
        if len(frames) >= max_frames:
            break
    return frames


# ---------------------------------------------------------------------------
# _parse_last_event_id
# ---------------------------------------------------------------------------


def test_parse_last_event_id_none_returns_zero() -> None:
    assert _parse_last_event_id(None) == 0


def test_parse_last_event_id_empty_returns_zero() -> None:
    assert _parse_last_event_id("") == 0


def test_parse_last_event_id_valid_int() -> None:
    assert _parse_last_event_id("7") == 7


def test_parse_last_event_id_malformed_falls_back_to_zero() -> None:
    assert _parse_last_event_id("not-a-number") == 0


def test_parse_last_event_id_negative_clamped_to_zero() -> None:
    assert _parse_last_event_id("-5") == 0


# ---------------------------------------------------------------------------
# event_stream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_yields_events_then_terminates_on_stopped() -> None:
    run_id = uuid4()
    svc = FakeEventService(
        batches=[
            [_ev(1, "ToolCalled"), _ev(2, "EvidenceAdded")],
            [_ev(3, "Stopped", stop_reason="judge_confirmed")],
        ]
    )
    frames = await _collect(
        event_stream(
            run_id,
            svc,
            cancellation=ConnectionManager(),
            poll_interval_s=0.0,
            heartbeat_ticks=1000,
        ),
    )
    assert [f["event"] for f in frames] == ["ToolCalled", "EvidenceAdded", "Stopped"]
    assert frames[0]["id"] == "1"
    assert frames[-1]["id"] == "3"
    payload = json.loads(frames[2]["data"])
    assert payload["stop_reason"] == "judge_confirmed"


@pytest.mark.asyncio
async def test_stream_resume_skips_events_at_or_below_last_event_id() -> None:
    run_id = uuid4()
    svc = FakeEventService(
        batches=[
            [_ev(5, "ToolCalled"), _ev(6, "EvidenceAdded"), _ev(7, "Stopped")],
        ]
    )
    frames = await _collect(
        event_stream(
            run_id,
            svc,
            last_event_id="5",
            cancellation=ConnectionManager(),
            poll_interval_s=0.0,
            heartbeat_ticks=1000,
        ),
    )
    assert [f["id"] for f in frames] == ["6", "7"]
    # The very first call must use after_step=5.
    assert svc.calls[0][1] == 5


@pytest.mark.asyncio
async def test_stream_emits_heartbeat_after_idle_ticks() -> None:
    run_id = uuid4()
    # Two idle polls between the first event and the Stopped event give the
    # idle counter time to reach ``heartbeat_ticks`` and trigger a heartbeat.
    svc = FakeEventService(
        batches=[
            [_ev(1, "ToolCalled")],
            [],
            [],
            [_ev(2, "Stopped")],
        ]
    )
    frames = await _collect(
        event_stream(
            run_id,
            svc,
            cancellation=ConnectionManager(),
            poll_interval_s=0.0,
            heartbeat_ticks=2,
        ),
    )
    types = [f["event"] for f in frames]
    assert "heartbeat" in types
    # Heartbeat occurs between the first real event and the Stopped event.
    assert types.index("heartbeat") > types.index("ToolCalled")


@pytest.mark.asyncio
async def test_stream_heartbeat_resets_on_real_event() -> None:
    run_id = uuid4()
    # Pattern: event, 3 idle polls (one heartbeat fires after 3 ticks),
    # then Stopped. If heartbeat had NOT reset on the event, we would see
    # multiple heartbeats.
    svc = FakeEventService(
        batches=[
            [_ev(1, "ToolCalled")],
            [],
            [],
            [],
            [_ev(2, "Stopped")],
        ]
    )
    frames = await _collect(
        event_stream(
            run_id,
            svc,
            cancellation=ConnectionManager(),
            poll_interval_s=0.0,
            heartbeat_ticks=3,
        ),
    )
    assert [f["event"] for f in frames].count("heartbeat") == 1


@pytest.mark.asyncio
async def test_stream_breaks_on_cancellation_with_synthetic_frame() -> None:
    run_id = uuid4()
    mgr = ConnectionManager()
    mgr.cancel(run_id)
    svc = FakeEventService(batches=[[_ev(1, "ToolCalled")]])
    frames = await _collect(
        event_stream(
            run_id,
            svc,
            cancellation=mgr,
            poll_interval_s=0.0,
            heartbeat_ticks=1000,
        ),
    )
    # The cancel branch drains the pending events first, then emits ``cancelled``.
    assert [f["event"] for f in frames] == ["ToolCalled", "cancelled"]
    assert frames[-1]["data"] == "{}"
    assert frames[-1]["id"] == "1"


@pytest.mark.asyncio
async def test_stream_cancellation_with_no_pending_events() -> None:
    run_id = uuid4()
    mgr = ConnectionManager()
    mgr.cancel(run_id)
    svc = FakeEventService(batches=[])
    frames = await _collect(
        event_stream(
            run_id,
            svc,
            cancellation=mgr,
            poll_interval_s=0.0,
            heartbeat_ticks=1000,
        ),
    )
    assert [f["event"] for f in frames] == ["cancelled"]
    assert frames[-1]["id"] == "0"


@pytest.mark.asyncio
async def test_stream_empty_polls_then_event_then_stop() -> None:
    run_id = uuid4()
    # Several empty polls before the first real event arrives.
    svc = FakeEventService(
        batches=[
            [],
            [],
            [_ev(1, "ToolCalled")],
            [_ev(2, "Stopped")],
        ]
    )
    frames = await _collect(
        event_stream(
            run_id,
            svc,
            cancellation=ConnectionManager(),
            poll_interval_s=0.0,
            heartbeat_ticks=1000,
        ),
    )
    assert [f["event"] for f in frames] == ["ToolCalled", "Stopped"]


@pytest.mark.asyncio
async def test_stream_malformed_last_event_id_starts_at_zero() -> None:
    run_id = uuid4()
    svc = FakeEventService(batches=[[_ev(1, "Stopped")]])
    frames = await _collect(
        event_stream(
            run_id,
            svc,
            last_event_id="banana",
            cancellation=ConnectionManager(),
            poll_interval_s=0.0,
            heartbeat_ticks=1000,
        ),
    )
    assert svc.calls[0][1] == 0
    assert [f["id"] for f in frames] == ["1"]


@pytest.mark.asyncio
async def test_stream_advances_after_step_across_batches() -> None:
    run_id = uuid4()
    svc = FakeEventService(
        batches=[
            [_ev(1, "ToolCalled")],
            [_ev(2, "EvidenceAdded")],
            [_ev(3, "Stopped")],
        ]
    )
    await _collect(
        event_stream(
            run_id,
            svc,
            cancellation=ConnectionManager(),
            poll_interval_s=0.0,
            heartbeat_ticks=1000,
        ),
    )
    # Second call must request after_step=1 (the highest seen so far).
    assert svc.calls[1][1] == 1
    assert svc.calls[2][1] == 2

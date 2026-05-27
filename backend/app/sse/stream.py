"""SSE event stream generator (RF-08).

Reads from the append-only ``events`` table via ``EventService.get_events``
and yields ``sse_starlette``-compatible dict frames.

Termination contract (IP-10 §3 O-05):

* A real ``Stopped`` event ends the stream after being yielded.
* ``connection_manager.is_cancelled(run_id)`` ends the stream after a synthetic
  ``event: cancelled`` frame is emitted. The synthetic frame is **not**
  persisted as a DB event.

Heartbeat (IP-10 §3 O-04):

* The poll interval is fixed at ``POLL_INTERVAL_S`` (0.25 s in production).
* A heartbeat counter measured in loop ticks (``HEARTBEAT_TICKS`` = 60 → 15 s)
  is reset on every real event yielded, so heartbeats pause naturally under
  load. Both constants are injectable for deterministic tests.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

logger = structlog.get_logger()


POLL_INTERVAL_S: float = 0.25
"""How long the stream waits between DB polls when no events are pending."""

HEARTBEAT_TICKS: int = 60
"""Number of idle poll loops before emitting a heartbeat (60 × 0.25 s = 15 s)."""


class _CancellationProbe(Protocol):
    """Minimal surface required from ``connection_manager`` by the stream."""

    def is_cancelled(self, run_id: UUID) -> bool: ...


class _EventReader(Protocol):
    """Minimal surface required from ``EventService`` by the stream."""

    async def get_events(
        self,
        run_id: UUID,
        after_step: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...


def _parse_last_event_id(raw: str | None) -> int:
    """Parse the ``Last-Event-ID`` value to an ``after_step`` integer.

    A malformed value resets the cursor to 0 (BRD-10 §4.2 / IP-10 R-05).
    """
    if not raw:
        return 0
    try:
        return max(int(raw), 0)
    except ValueError:
        return 0


async def event_stream(
    run_id: UUID,
    event_service: _EventReader,
    last_event_id: str | None = None,
    *,
    cancellation: _CancellationProbe | None = None,
    poll_interval_s: float = POLL_INTERVAL_S,
    heartbeat_ticks: int = HEARTBEAT_TICKS,
    batch_limit: int = 50,
) -> AsyncIterator[dict[str, Any]]:
    """Yield SSE frames for ``run_id`` until termination.

    Frames are plain dicts compatible with ``sse_starlette.EventSourceResponse``::

        {"event": "<name>", "data": "<json>", "id": "<step_index>"}
    """
    # Late import to avoid a circular module load at startup time.
    if cancellation is None:
        from app.sse.manager import connection_manager as _default_manager

        cancellation = _default_manager

    after_step = _parse_last_event_id(last_event_id)
    idle_ticks = 0
    last_seen = after_step

    logger.info(
        "sse_stream_start",
        run_id=str(run_id),
        after_step=after_step,
    )

    while True:
        if cancellation.is_cancelled(run_id):
            # Drain any events that landed between the last poll and the cancel
            # signal so the client sees the full prefix before the synthetic
            # ``cancelled`` frame.
            tail = await event_service.get_events(
                run_id=run_id, after_step=after_step, limit=batch_limit
            )
            for event in tail:
                step = int(event.get("step_index") or 0)
                yield {
                    "event": str(event.get("type") or "message"),
                    "data": json.dumps(event),
                    "id": str(step),
                }
                last_seen = max(last_seen, step)
                after_step = last_seen
            yield {
                "event": "cancelled",
                "data": "{}",
                "id": str(last_seen),
            }
            logger.info("sse_stream_cancelled", run_id=str(run_id))
            return

        events = await event_service.get_events(
            run_id=run_id, after_step=after_step, limit=batch_limit
        )

        stopped = False
        if events:
            idle_ticks = 0
            for event in events:
                step = int(event.get("step_index") or 0)
                event_type = str(event.get("type") or "message")
                yield {
                    "event": event_type,
                    "data": json.dumps(event),
                    "id": str(step),
                }
                last_seen = max(last_seen, step)
                after_step = last_seen
                if event_type == "Stopped":
                    stopped = True

        if stopped:
            logger.info("sse_stream_complete", run_id=str(run_id))
            return

        idle_ticks += 1
        if idle_ticks >= heartbeat_ticks:
            yield {
                "event": "heartbeat",
                "data": "",
                "id": str(last_seen),
            }
            idle_ticks = 0

        await asyncio.sleep(poll_interval_s)

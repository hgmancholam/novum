"""In-process SSE connection manager (RF-08, RF-05).

A single concrete class — deliberately not a Protocol seam. The single-worker
constraint (``uvicorn --workers 1``) guarantees process-local state is the
ground truth.

The manager tracks three pieces of state per ``run_id``:

* the set of active connection ids (for observability / disconnect bookkeeping),
* a boolean cancellation flag (for live cancellation from another coroutine),
* a list of bounded subscriber queues used for live event fan-out from the
  agent runner (BRD-19 §4.9).
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger()


# Per-queue cap (BRD-19 §9). When a subscriber is slow we drop the oldest item
# rather than block the publisher; the BRD-10 DB poll loop preserves
# correctness end-to-end.
_QUEUE_MAXSIZE = 1000


class ConnectionManager:
    """Tracks active SSE connections, cancellation flags and subscribers per run."""

    def __init__(self) -> None:
        self._connections: dict[UUID, set[str]] = {}
        self._cancelled: dict[UUID, bool] = {}
        self._subscribers: dict[UUID, list[asyncio.Queue[dict[str, Any]]]] = {}

    def connect(self, run_id: UUID, connection_id: str) -> None:
        """Register a new active connection for ``run_id``."""
        bucket = self._connections.setdefault(run_id, set())
        bucket.add(connection_id)
        logger.debug(
            "sse_connect",
            run_id=str(run_id),
            connection_id=connection_id,
            active=len(bucket),
        )

    def disconnect(self, run_id: UUID, connection_id: str) -> None:
        """Remove an active connection. Idempotent — unknown ids are ignored."""
        bucket = self._connections.get(run_id)
        if bucket is None:
            return
        bucket.discard(connection_id)
        if not bucket:
            del self._connections[run_id]
        logger.debug(
            "sse_disconnect",
            run_id=str(run_id),
            connection_id=connection_id,
            active=len(bucket),
        )

    def cancel(self, run_id: UUID) -> None:
        """Signal cancellation for ``run_id``. Idempotent."""
        self._cancelled[run_id] = True
        logger.info("sse_cancelled", run_id=str(run_id))

    def is_cancelled(self, run_id: UUID) -> bool:
        """Return whether cancellation has been requested for ``run_id``."""
        return self._cancelled.get(run_id, False)

    def clear_cancelled(self, run_id: UUID) -> None:
        """Clear the cancellation flag for ``run_id``."""
        self._cancelled.pop(run_id, None)

    def active_connections(self, run_id: UUID) -> int:
        """Return the current number of active connections for ``run_id``."""
        return len(self._connections.get(run_id, set()))

    def subscribe(self, run_id: UUID) -> asyncio.Queue[dict[str, Any]]:
        """Return a per-connection bounded queue for live event fan-out."""
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subscribers.setdefault(run_id, []).append(q)
        return q

    def unsubscribe(
        self, run_id: UUID, queue: asyncio.Queue[dict[str, Any]]
    ) -> None:
        """Detach a subscriber queue. Idempotent."""
        subs = self._subscribers.get(run_id)
        if not subs:
            return
        with contextlib.suppress(ValueError):
            subs.remove(queue)
        if not subs:
            del self._subscribers[run_id]

    async def publish(self, run_id: UUID, event: dict[str, Any]) -> None:
        """Best-effort fan-out. Full queues drop the oldest item + log overflow."""
        for q in list(self._subscribers.get(run_id, [])):
            if q.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()
                logger.warning("sse_queue_overflow", run_id=str(run_id))
            q.put_nowait(event)

    def reset(self) -> None:
        """Drop all state. Intended for test isolation only."""
        self._connections.clear()
        self._cancelled.clear()
        self._subscribers.clear()


connection_manager = ConnectionManager()

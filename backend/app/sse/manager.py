"""In-process SSE connection manager (RF-08, RF-05).

A single concrete class — deliberately not a Protocol seam. The single-worker
constraint (``uvicorn --workers 1``) guarantees process-local state is the
ground truth.

The manager tracks two pieces of state per ``run_id``:

* the set of active connection ids (for observability / disconnect bookkeeping),
* a boolean cancellation flag (for live cancellation from another coroutine).

It exposes only synchronous methods: every operation mutates an in-memory dict
and never performs IO.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger()


class ConnectionManager:
    """Tracks active SSE connections and cancellation flags per run."""

    def __init__(self) -> None:
        self._connections: dict[UUID, set[str]] = {}
        self._cancelled: dict[UUID, bool] = {}

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

    def reset(self) -> None:
        """Drop all state. Intended for test isolation only."""
        self._connections.clear()
        self._cancelled.clear()


connection_manager = ConnectionManager()

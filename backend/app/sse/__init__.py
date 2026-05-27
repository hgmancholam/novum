"""SSE transport package (RF-08)."""

from __future__ import annotations

from app.sse.manager import ConnectionManager, connection_manager
from app.sse.stream import HEARTBEAT_TICKS, POLL_INTERVAL_S, event_stream

__all__ = [
    "HEARTBEAT_TICKS",
    "POLL_INTERVAL_S",
    "ConnectionManager",
    "connection_manager",
    "event_stream",
]

"""Event streaming endpoint (RF-08).

Replaces the HTTP-501 stub with a production SSE stream. The route is
public-by-URL (RF-05) — no auth dependency — matching ``GET /api/runs/{id}``.

Resume contract (IP-10 §3 O-02):

* ``?last_event_id=<step>`` query parameter is the **primary** signal because
  browser ``EventSource`` clients cannot set custom request headers.
* ``Last-Event-ID`` request header is honoured as a fallback for non-browser
  clients (httpx, server-to-server).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.dependencies import DbSession
from app.services.event_service import EventService
from app.sse import connection_manager, event_stream

router = APIRouter(prefix="/api/runs", tags=["Events"])


@router.get("/{run_id}/events")
async def stream_events(
    run_id: UUID,
    request: Request,  # noqa: ARG001 — kept for future per-request introspection
    db: DbSession,
    last_event_id: Annotated[
        str | None,
        Query(alias="last_event_id"),
    ] = None,
    last_event_id_header: Annotated[
        str | None,
        Header(alias="Last-Event-ID", convert_underscores=False),
    ] = None,
) -> EventSourceResponse:
    """Stream events for a run via SSE (RF-08)."""
    event_service = EventService(db)
    connection_id = str(uuid4())
    resume_from = last_event_id or last_event_id_header

    async def generate() -> AsyncIterator[dict[str, Any]]:
        connection_manager.connect(run_id, connection_id)
        try:
            async for frame in event_stream(
                run_id=run_id,
                event_service=event_service,
                last_event_id=resume_from,
            ):
                yield frame
        finally:
            connection_manager.disconnect(run_id, connection_id)

    return EventSourceResponse(
        generate(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

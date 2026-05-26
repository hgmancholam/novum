"""Event streaming endpoint (SSE).

This is a placeholder. The actual implementation lands in BRD-10.
We return HTTP 501 (Not Implemented) — not a 500 — so callers and
tests can distinguish "deferred feature" from "runtime error".
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request

from app.dependencies import DbSession

router = APIRouter(prefix="/api/runs", tags=["Events"])


@router.get("/{run_id}/events")
async def stream_events(
    run_id: UUID,
    request: Request,
    db: DbSession,
    last_event_id: Annotated[
        str | None,
        Header(alias="Last-Event-ID", convert_underscores=False),
    ] = None,
) -> None:
    """Stream events for a run via SSE.

    The `Last-Event-ID` header is read per the EventSource spec for
    resume on reconnect. Full implementation in BRD-10.
    """
    raise HTTPException(
        status_code=501,
        detail="SSE streaming not implemented yet (BRD-10)",
    )

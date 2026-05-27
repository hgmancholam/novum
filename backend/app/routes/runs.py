"""Run management endpoints (BRD-03 §4.7).

Note on auth: `GET /api/runs/{id}` is intentionally NOT guarded by the
`X-Username` dependency because RF-05 specifies runs are public-by-URL.
All other endpoints require an authenticated user.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.dependencies import CurrentUsername, DbSession
from app.domain.run import RunCreate, RunForkRequest, RunListItem, RunResponse
from app.services.run_service import RunService

router = APIRouter(prefix="/api/runs", tags=["Runs"])


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    data: RunCreate,
    db: DbSession,
    username: CurrentUsername,
) -> RunResponse:
    """Create a new research run (RF-01)."""
    service = RunService(db)
    return await service.create_run(data, username)


@router.get("", response_model=list[RunListItem])
async def list_runs(
    db: DbSession,
    _username: CurrentUsername,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[RunListItem]:
    """List recent runs for all users — auth required (RF-09)."""
    service = RunService(db)
    return await service.list_runs(limit, offset)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: UUID,
    db: DbSession,
) -> RunResponse:
    """Get a run by ID — public-by-URL per RF-05."""
    service = RunService(db)
    return await service.get_run(run_id)


@router.post("/{run_id}/fork", response_model=RunResponse, status_code=201)
async def fork_run(
    run_id: UUID,
    data: RunForkRequest,
    db: DbSession,
    username: CurrentUsername,
) -> RunResponse:
    """Fork a run from a specific event (RF-03)."""
    service = RunService(db)
    return await service.fork_run(run_id, data, username)


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    run_id: UUID,
    db: DbSession,
    username: CurrentUsername,
) -> RunResponse:
    """Cancel a running run (RF-08)."""
    service = RunService(db)
    return await service.cancel_run(run_id, username)


@router.post("/{run_id}/resume", response_model=RunResponse)
async def resume_run(
    run_id: UUID,
    db: DbSession,
    username: CurrentUsername,
) -> RunResponse:
    """Resume a stopped/errored run (RF-11)."""
    service = RunService(db)
    return await service.resume_run(run_id, username)

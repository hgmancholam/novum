# BRD-03: FastAPI Core & API Skeleton

**Document ID:** BRD-03
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 4 of 19

---

## 1. Executive Summary

Implement the FastAPI router structure, CRUD services, and API endpoints for runs and events. This BRD establishes the API contract that the frontend consumes, including proper error handling and OpenAPI documentation.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-08 | SSE streaming endpoint | Partial (structure only) |
| RF-09 | Run discovery (list + URL) | Complete |
| RF-03 | Fork endpoint | Complete |
| RF-11 | Resume endpoint | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-01, BRD-02 | BRD-04, BRD-10, BRD-11 |

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    routes/
      __init__.py
      health.py           # Health check
      runs.py             # Run CRUD + fork/resume
      events.py           # Event streaming (SSE)
    services/
      __init__.py
      run_service.py      # Run business logic
      event_service.py    # Event persistence
    dependencies.py       # FastAPI dependencies
    exceptions.py         # Custom exceptions
    main.py               # Updated with routers
```

### 4.2 API Endpoints

| Method | Path | Request Body | Response | Description | RF |
|--------|------|--------------|----------|-------------|-----|
| GET | `/health` | — | `{"status": "ok"}` | Health check | — |
| POST | `/api/runs` | `RunCreate` | `RunResponse` | Create new run | RF-01 |
| GET | `/api/runs` | — | `List[RunListItem]` | List recent runs | RF-09 |
| GET | `/api/runs/{id}` | — | `RunResponse` | Get run by ID | RF-02 |
| GET | `/api/runs/{id}/events` | — | SSE stream | Stream events | RF-08 |
| POST | `/api/runs/{id}/fork` | `RunForkRequest` | `RunResponse` | Fork from event | RF-03 |
| POST | `/api/runs/{id}/resume` | — | `RunResponse` | Resume stopped run | RF-11 |
| POST | `/api/runs/{id}/cancel` | — | `RunResponse` | Cancel running | RF-08 |

### 4.3 Dependencies

#### backend/app/dependencies.py

```python
"""FastAPI dependencies for dependency injection."""

from typing import Annotated, AsyncIterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a database session."""
    async with async_session_maker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_username(
    x_username: Annotated[str | None, Header()] = None,
) -> str:
    """Extract username from header.
    
    For V1, we use a simple header-based auth.
    Production should use proper token validation (BRD-04).
    """
    if not x_username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Username header required",
        )
    return x_username


CurrentUsername = Annotated[str, Depends(get_current_username)]
```

### 4.4 Custom Exceptions

#### backend/app/exceptions.py

```python
"""Custom exceptions for API error handling."""

from fastapi import HTTPException, status


class RunNotFoundError(HTTPException):
    """Run does not exist."""

    def __init__(self, run_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )


class EventNotFoundError(HTTPException):
    """Event does not exist."""

    def __init__(self, event_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )


class RunNotForkableError(HTTPException):
    """Run cannot be forked from this event."""

    def __init__(self, event_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Event {event_id} is not a forkable point",
        )


class RunAlreadyStoppedError(HTTPException):
    """Run has already stopped."""

    def __init__(self, run_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run {run_id} has already stopped",
        )


class RunStillRunningError(HTTPException):
    """Run is still running (cannot resume)."""

    def __init__(self, run_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run {run_id} is still running",
        )


class UnauthorizedError(HTTPException):
    """User not authorized for this operation."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )
```

### 4.5 Run Service

#### backend/app/services/run_service.py

```python
"""Run business logic and persistence."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import StopReason
from app.domain.events import FORKABLE_EVENTS
from app.domain.run import RunCreate, RunForkRequest, RunListItem, RunResponse
from app.exceptions import (
    EventNotFoundError,
    RunAlreadyStoppedError,
    RunNotForkableError,
    RunNotFoundError,
    RunStillRunningError,
)
from app.models import Event, Run


class RunService:
    """Service for run operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_run(self, data: RunCreate, username: str) -> RunResponse:
        """Create a new research run."""
        run = Run(
            owner_username=username,
            question=data.question,
            user_context=data.user_context,
            output_format=data.output_format.value,
            confidence_threshold=data.confidence_threshold,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return RunResponse.model_validate(run)

    async def get_run(self, run_id: UUID) -> RunResponse:
        """Get a run by ID."""
        run = await self.db.get(Run, run_id)
        if not run:
            raise RunNotFoundError(str(run_id))
        return RunResponse.model_validate(run)

    async def list_runs(
        self,
        username: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[RunListItem]:
        """List recent runs for a user (RF-09)."""
        query = (
            select(Run)
            .where(Run.owner_username == username)
            .order_by(Run.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        runs = result.scalars().all()
        return [
            RunListItem(
                id=r.id,
                question=r.question[:100] + "..." if len(r.question) > 100 else r.question,
                started_at=r.started_at,
                stopped_at=r.stopped_at,
                stop_reason=StopReason(r.stop_reason) if r.stop_reason else None,
            )
            for r in runs
        ]

    async def fork_run(
        self,
        run_id: UUID,
        data: RunForkRequest,
        username: str,
    ) -> RunResponse:
        """Fork a run from a specific event (RF-03)."""
        # Get original run
        original = await self.db.get(Run, run_id)
        if not original:
            raise RunNotFoundError(str(run_id))

        # Get fork point event
        event = await self.db.get(Event, data.event_id)
        if not event:
            raise EventNotFoundError(str(data.event_id))

        # Check if event is forkable
        if event.type not in [e.value for e in FORKABLE_EVENTS]:
            raise RunNotForkableError(str(data.event_id))

        # Create forked run
        forked = Run(
            owner_username=username,
            question=original.question,
            user_context=original.user_context,
            output_format=original.output_format,
            confidence_threshold=original.confidence_threshold,
            parent_run_id=run_id,
            forked_at_event_id=data.event_id,
        )
        self.db.add(forked)
        await self.db.commit()
        await self.db.refresh(forked)
        return RunResponse.model_validate(forked)

    async def cancel_run(self, run_id: UUID, username: str) -> RunResponse:
        """Cancel a running run (RF-08)."""
        run = await self.db.get(Run, run_id)
        if not run:
            raise RunNotFoundError(str(run_id))

        if run.stop_reason is not None:
            raise RunAlreadyStoppedError(str(run_id))

        run.stop_reason = StopReason.USER_CANCELLED.value
        run.stopped_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(run)
        return RunResponse.model_validate(run)

    async def resume_run(self, run_id: UUID, username: str) -> RunResponse:
        """Resume a stopped run (RF-11)."""
        run = await self.db.get(Run, run_id)
        if not run:
            raise RunNotFoundError(str(run_id))

        if run.stop_reason is None:
            raise RunStillRunningError(str(run_id))

        # Only certain stop reasons are resumable
        resumable = {
            StopReason.USER_CANCELLED.value,
            StopReason.ERRORED.value,
        }
        if run.stop_reason not in resumable:
            raise RunAlreadyStoppedError(str(run_id))

        # Clear stop state to resume
        run.stop_reason = None
        run.stopped_at = None
        await self.db.commit()
        await self.db.refresh(run)
        return RunResponse.model_validate(run)
```

### 4.6 Event Service

#### backend/app/services/event_service.py

```python
"""Event persistence and retrieval."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.events import BaseEvent, Event as EventUnion, EVENT_TYPE_MAP
from app.models import Event


class EventService:
    """Service for event operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def append_event(
        self,
        run_id: UUID,
        event: BaseEvent,
        parent_event_id: Optional[UUID] = None,
    ) -> Event:
        """Append an event to a run's event log.
        
        Events are append-only — never update or delete.
        """
        # Get next step index
        query = (
            select(Event.step_index)
            .where(Event.run_id == run_id)
            .order_by(Event.step_index.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        last_index = result.scalar()
        next_index = (last_index or 0) + 1

        # Create event record
        db_event = Event(
            run_id=run_id,
            step_index=next_index,
            parent_event_id=parent_event_id,
            type=event.type,
            payload=event.model_dump(exclude={"id", "run_id", "step_index", "parent_event_id", "created_at"}),
        )
        self.db.add(db_event)
        await self.db.commit()
        await self.db.refresh(db_event)
        return db_event

    async def get_events(
        self,
        run_id: UUID,
        after_step: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get events for a run, optionally after a step index.
        
        Returns raw dict format for SSE streaming.
        """
        query = (
            select(Event)
            .where(Event.run_id == run_id)
            .where(Event.step_index > after_step)
            .order_by(Event.step_index)
            .limit(limit)
        )
        result = await self.db.execute(query)
        events = result.scalars().all()
        
        return [
            {
                "id": str(e.id),
                "run_id": str(e.run_id),
                "step_index": e.step_index,
                "parent_event_id": str(e.parent_event_id) if e.parent_event_id else None,
                "type": e.type,
                "created_at": e.created_at.isoformat(),
                **e.payload,
            }
            for e in events
        ]

    async def get_event(self, event_id: UUID) -> Optional[Event]:
        """Get a single event by ID."""
        return await self.db.get(Event, event_id)
```

### 4.7 Routes

#### backend/app/routes/health.py

```python
"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
```

#### backend/app/routes/runs.py

```python
"""Run management endpoints."""

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
    """Create a new research run."""
    service = RunService(db)
    return await service.create_run(data, username)


@router.get("", response_model=list[RunListItem])
async def list_runs(
    db: DbSession,
    username: CurrentUsername,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[RunListItem]:
    """List recent runs for the current user (RF-09)."""
    service = RunService(db)
    return await service.list_runs(username, limit, offset)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: UUID,
    db: DbSession,
) -> RunResponse:
    """Get a run by ID."""
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
```

#### backend/app/routes/events.py

```python
"""Event streaming endpoint (SSE)."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.dependencies import DbSession

# SSE implementation is in BRD-10
# This is a placeholder structure

router = APIRouter(prefix="/api/runs", tags=["Events"])


@router.get("/{run_id}/events")
async def stream_events(
    run_id: UUID,
    request: Request,
    db: DbSession,
    last_event_id: str | None = Query(None, alias="Last-Event-ID"),
) -> None:
    """Stream events for a run via SSE.
    
    Full implementation in BRD-10.
    """
    # Placeholder - actual SSE in BRD-10
    raise NotImplementedError("SSE streaming implemented in BRD-10")
```

#### backend/app/routes/__init__.py

```python
"""API routes package."""

from fastapi import APIRouter

from app.routes.health import router as health_router
from app.routes.runs import router as runs_router
from app.routes.events import router as events_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(runs_router)
api_router.include_router(events_router)

__all__ = ["api_router"]
```

### 4.8 Updated Main

#### backend/app/main.py (updated)

```python
"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import settings
from app.database import engine
from app.routes import api_router


structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown."""
    logger.info("starting_novum", host=settings.host, port=settings.port)
    yield
    await engine.dispose()
    logger.info("shutdown_complete")


app = FastAPI(
    title="Novum API",
    description="Self-directing research agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configured per-environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(api_router)
```

---

## 5. Acceptance Criteria

### AC-01: Create Run Works
```gherkin
Given a valid user header X-Username: testuser
When I POST /api/runs with valid RunCreate body
Then status 201 is returned
  And the response contains the run ID
  And the run is persisted in the database
```

### AC-02: List Runs Returns Recent
```gherkin
Given user "testuser" has 5 runs
When I GET /api/runs with X-Username: testuser
Then status 200 is returned
  And the response contains 5 RunListItem objects
  And runs are ordered by started_at DESC
```

### AC-03: Fork Creates New Run
```gherkin
Given run A exists with a PlanCreated event
When I POST /api/runs/{A}/fork with that event ID
Then status 201 is returned
  And a new run B is created
  And B.parent_run_id equals A.id
  And B.forked_at_event_id equals the event ID
```

### AC-04: Cancel Updates Stop Reason
```gherkin
Given a running run (stop_reason = NULL)
When I POST /api/runs/{id}/cancel
Then status 200 is returned
  And stop_reason equals "user_cancelled"
  And stopped_at is set
```

### AC-05: Resume Clears Stop State
```gherkin
Given a cancelled run (stop_reason = "user_cancelled")
When I POST /api/runs/{id}/resume
Then status 200 is returned
  And stop_reason is NULL
  And stopped_at is NULL
```

---

## 6. Implementation Checklist

- [ ] Create `backend/app/dependencies.py`
- [ ] Create `backend/app/exceptions.py`
- [ ] Create `backend/app/services/__init__.py`
- [ ] Create `backend/app/services/run_service.py`
- [ ] Create `backend/app/services/event_service.py`
- [ ] Create `backend/app/routes/health.py`
- [ ] Create `backend/app/routes/runs.py`
- [ ] Create `backend/app/routes/events.py` (placeholder)
- [ ] Create `backend/app/routes/__init__.py`
- [ ] Update `backend/app/main.py` with routers
- [ ] Write unit tests for RunService
- [ ] Write integration tests for routes
- [ ] Verify OpenAPI docs at /docs

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | pytest | RunService, EventService | 100% |
| Integration | pytest + httpx | All routes | 100% |
| API Contract | OpenAPI | /docs endpoint | Manual |

## 8. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection |

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Missing auth check | High | Medium | Middleware + tests |
| Race condition on cancel | Med | Low | Database-level locking |
| Large event payloads | Med | Medium | Payload size limits |

## 10. Out of Scope

- SSE streaming implementation (BRD-10)
- User authentication (BRD-04)
- Agent execution (BRD-07)
- Event generation (BRD-07, BRD-08, BRD-09)

"""Run business logic and persistence."""

from __future__ import annotations

from datetime import UTC, datetime
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
from app.sse.manager import connection_manager

# Stop reasons that can be resumed (RF-11).
_RESUMABLE: frozenset[str] = frozenset(
    {StopReason.USER_CANCELLED.value, StopReason.ERRORED.value}
)


class RunService:
    """Service for run operations (BRD-03 §4.5)."""

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
        """Get a run by ID (public-by-URL per RF-05)."""
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
        """List recent runs for a user (RF-09).

        The question is truncated at 100 chars with an ellipsis suffix —
        the history panel (BRD-12) depends on this exact behavior.
        """
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
                question=(
                    r.question[:100] + "..." if len(r.question) > 100 else r.question
                ),
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
        original = await self.db.get(Run, run_id)
        if not original:
            raise RunNotFoundError(str(run_id))

        event = await self.db.get(Event, data.event_id)
        if not event:
            raise EventNotFoundError(str(data.event_id))

        forkable_values = {e.value for e in FORKABLE_EVENTS}
        if event.type not in forkable_values:
            raise RunNotForkableError(str(data.event_id))

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
        run.stopped_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(run)
        # Notify any in-flight SSE generators for this run (RF-08 / IP-10 §3 O-05).
        connection_manager.cancel(run_id)
        return RunResponse.model_validate(run)

    async def resume_run(self, run_id: UUID, username: str) -> RunResponse:
        """Resume a stopped run (RF-11).

        Only `user_cancelled` and `errored` runs are resumable;
        honest stops and `judge_confirmed` are terminal.
        """
        run = await self.db.get(Run, run_id)
        if not run:
            raise RunNotFoundError(str(run_id))

        if run.stop_reason is None:
            raise RunStillRunningError(str(run_id))

        if run.stop_reason not in _RESUMABLE:
            raise RunAlreadyStoppedError(str(run_id))

        run.stop_reason = None
        run.stopped_at = None
        await self.db.commit()
        await self.db.refresh(run)
        return RunResponse.model_validate(run)

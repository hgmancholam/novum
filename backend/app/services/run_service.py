"""Run business logic and persistence."""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

# NOTE: `agent_runner` is imported lazily inside the methods that use it to
# break the circular import chain  app.agent.runner → app.services.event_service
# → app.services.__init__ → app.services.run_service → app.agent.runner.
from app.domain.enums import EventType, StopReason
from app.domain.events import (
    FORKABLE_EVENTS,
    ResumedAfterCancelEvent,
    ResumedAfterErrorEvent,
)
from app.domain.run import (
    RunCreate,
    RunForkRequest,
    RunListItem,
    RunListPage,
    RunResponse,
)
from app.exceptions import (
    EventNotFoundError,
    InvalidCursorError,
    RunAlreadyStoppedError,
    RunNotFinishedError,
    RunNotForkableError,
    RunNotFoundError,
    RunStillRunningError,
    RunStillTerminatingError,
)
from app.models import Event, Run
from app.services.event_service import EventService
from app.sse.manager import connection_manager

# Stop reasons that can be resumed (RF-11).
_RESUMABLE: frozenset[str] = frozenset(
    {StopReason.USER_CANCELLED.value, StopReason.ERRORED.value}
)


def _encode_cursor(started_at: datetime, run_id: UUID) -> str:
    """Encode ``(started_at, id)`` as an opaque base64 cursor (BRD-20 §4.4)."""
    raw = f"{started_at.isoformat()}|{run_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """Decode an opaque cursor. Raises ``InvalidCursorError`` on tamper."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        iso, uuid_str = raw.split("|", 1)
        started_at = datetime.fromisoformat(iso)
        run_id = UUID(uuid_str)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise InvalidCursorError() from exc
    return started_at, run_id


def _to_list_item(r: Run) -> RunListItem:
    return RunListItem(
        id=r.id,
        username=r.owner_username,
        question=(
            r.question[:100] + "..." if len(r.question) > 100 else r.question
        ),
        started_at=r.started_at,
        stopped_at=r.stopped_at,
        stop_reason=StopReason(r.stop_reason) if r.stop_reason else None,
        llm_provider=r.llm_provider,
    )


class RunService:
    """Service for run operations (BRD-03 §4.5)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_run(self, data: RunCreate, username: str) -> RunResponse:
        """Create a new research run."""
        from app.config import settings

        threshold = (
            data.confidence_threshold
            if data.confidence_threshold is not None
            else settings.confidence_threshold_default
        )
        run = Run(
            owner_username=username,
            question=data.question,
            user_context=data.user_context,
            output_format=data.output_format.value,
            confidence_threshold=threshold,
            llm_provider=data.llm_provider,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        # BRD-19 §4.4: hand off to the runner so the FSM starts emitting.
        from app.agent.runner import agent_runner

        await agent_runner.start(run.id)
        return RunResponse.model_validate(run)

    async def get_run(self, run_id: UUID) -> RunResponse:
        """Get a run by ID (public-by-URL per RF-05)."""
        run = await self.db.get(Run, run_id)
        if not run:
            raise RunNotFoundError(str(run_id))
        return RunResponse.model_validate(run)

    async def list_runs_keyset(
        self,
        username: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> RunListPage:
        """Keyset page over ``(started_at DESC, id DESC)``.

        Returns runs from all users (history is shared across the single
        server, consistent with RF-05 public-by-URL). When ``username`` is
        provided the result is filtered to that owner, kept for callers
        that still want an owner-scoped view.
        """
        query = (
            select(Run)
            .order_by(Run.started_at.desc(), Run.id.desc())
            .limit(limit + 1)
        )
        if username is not None:
            query = query.where(Run.owner_username == username)
        if cursor is not None:
            cur_ts, cur_id = _decode_cursor(cursor)
            # Tuple keyset: (started_at, id) < (cur_ts, cur_id) under DESC,DESC.
            # Some dialects (notably SQLite) lack row-value comparison, so we
            # expand it to the equivalent OR/AND form for portability.
            query = query.where(
                or_(
                    Run.started_at < cur_ts,
                    and_(Run.started_at == cur_ts, Run.id < cur_id),
                )
            )

        result = await self.db.execute(query)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor: str | None = None
        if has_more and page:
            last = page[-1]
            next_cursor = _encode_cursor(last.started_at, last.id)
        return RunListPage(
            items=[_to_list_item(r) for r in page],
            has_more=has_more,
            next_cursor=next_cursor,
        )

    async def delete_run(self, run_id: UUID) -> None:
        """Permanently delete a finished run.

        Public-by-URL per RF-05: any authenticated user can delete any
        finished run (the auth check lives at the route layer). Order:
        1. 404 if missing.
        2. Best-effort ``await_terminal`` (swallow ``RunStillTerminatingError``
           so the 409 body is never shadowed).
        3. 409 if still running (``stop_reason IS NULL``).
        4. Delete via ORM (cascades through events; ``runs.parent_run_id
           ON DELETE SET NULL`` orphans forks).
        5. Close any open SSE state (idempotent).
        """
        run = await self.db.get(Run, run_id)
        if run is None:
            raise RunNotFoundError(str(run_id))

        from app.agent.runner import agent_runner

        try:
            await agent_runner.await_terminal(run_id, timeout=2.0)
        except RunStillTerminatingError:
            # Fall through to the stop_reason guard — it owns the 409 body.
            pass

        # Re-read to capture any stop_reason flip that may have committed
        # while we awaited the terminal grace.
        await self.db.refresh(run)
        if run.stop_reason is None:
            raise RunNotFinishedError()

        await self.db.delete(run)
        await self.db.commit()
        connection_manager.close(run_id)

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

        # Cross-run guard (IP-15 B2): collapse to 404 so callers cannot probe
        # event IDs across runs to enumerate the event log.
        if event.run_id != run_id:
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
        # Symmetric with create_run / resume_run: hand off to the runner so
        # the forked FSM actually executes. Without this the row exists but
        # never produces events (IP-15 R-01 lineage is by reference; the
        # forked run starts with an empty event log and runs fresh).
        from app.agent.runner import agent_runner

        await agent_runner.start(forked.id)
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
        # BRD-19 §4.5: flip the orchestrator's cooperative cancel flag.
        from app.agent.runner import agent_runner

        agent_runner.cancel(run_id)
        return RunResponse.model_validate(run)

    async def resume_run(self, run_id: UUID, username: str) -> RunResponse:
        """Resume a stopped run (RF-11).

        Only `user_cancelled` and `errored` runs are resumable;
        honest stops and `judge_confirmed` are terminal.

        Emits the canonical `ResumedAfterError` / `ResumedAfterCancel` event
        (architecture.md §events) atomically with the `stop_reason` clear:
        the event is appended via `EventService.append_event(commit=False)`
        and a single `await self.db.commit()` covers both writes, so a
        failed append leaves `run.stop_reason` untouched (B1 atomicity).
        """
        # BRD-19 §4.6.1: wait for any in-flight task to settle (5s grace).
        # Raises RunStillTerminatingError (409) if the prior task does not
        # finish in time, so we never spawn a second writer concurrently.
        from app.agent.runner import agent_runner

        await agent_runner.await_terminal(run_id, timeout=5.0)

        run = await self.db.get(Run, run_id)
        if not run:
            raise RunNotFoundError(str(run_id))

        if run.stop_reason is None:
            raise RunStillRunningError(str(run_id))

        prior_stop_reason = run.stop_reason
        if prior_stop_reason not in _RESUMABLE:
            raise RunAlreadyStoppedError(str(run_id))

        # Locate the resume anchor by event TYPE (not recency) so the
        # invariant is grounded in the event log, not in clock skew.
        anchor = await self._find_resume_anchor(run_id, prior_stop_reason)
        if anchor is None:
            # Corrupt state: a run marked errored/user_cancelled with no
            # matching anchor event. Refuse to silently clear status.
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="resume anchor event not found",
            )

        event_service = EventService(self.db)
        resume_event: ResumedAfterErrorEvent | ResumedAfterCancelEvent
        match prior_stop_reason:
            case StopReason.ERRORED.value:
                resume_event = ResumedAfterErrorEvent(
                    original_error_event_id=anchor.id,
                    resume_point=f"after_step_{anchor.step_index}",
                )
            case StopReason.USER_CANCELLED.value:
                resume_event = ResumedAfterCancelEvent(
                    cancel_event_id=anchor.id,
                    resume_point=f"after_step_{anchor.step_index}",
                )
            case _:  # pragma: no cover — guarded by _RESUMABLE check above
                raise RunAlreadyStoppedError(str(run_id))

        await event_service.append_event(
            run_id,
            resume_event,
            parent_event_id=anchor.id,
            commit=False,
        )

        run.stop_reason = None
        run.stopped_at = None
        await self.db.commit()
        await self.db.refresh(run)
        # BRD-19 §4.6: re-launch the FSM after the ResumedAfter* anchor lands.
        await agent_runner.start(run_id)
        return RunResponse.model_validate(run)

    async def _find_resume_anchor(
        self, run_id: UUID, prior_stop_reason: str
    ) -> Event | None:
        """Locate the canonical anchor event for a resume (RF-11)."""
        if prior_stop_reason == StopReason.ERRORED.value:
            query = (
                select(Event)
                .where(Event.run_id == run_id)
                .where(Event.type == EventType.AGENT_ERRORED.value)
                .order_by(Event.step_index.desc())
                .limit(1)
            )
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        if prior_stop_reason == StopReason.USER_CANCELLED.value:
            # Filter the `stop_reason` key in Python to stay portable across
            # JSONB (Postgres) and JSON (SQLite, test) — a small fetch is
            # acceptable since `Stopped` events are at most one per run.
            query = (
                select(Event)
                .where(Event.run_id == run_id)
                .where(Event.type == EventType.STOPPED.value)
                .order_by(Event.step_index.desc())
            )
            result = await self.db.execute(query)
            for candidate in result.scalars():
                if (
                    candidate.payload.get("stop_reason")
                    == StopReason.USER_CANCELLED.value
                ):
                    return candidate
            return None
        return None  # pragma: no cover — guarded upstream

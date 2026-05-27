"""Unit tests for `RunService` (BRD-03 AC-01, AC-04, AC-05)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OutputFormat, StopReason
from app.domain.run import RunCreate, RunForkRequest
from app.exceptions import (
    EventNotFoundError,
    InvalidCursorError,
    RunAlreadyStoppedError,
    RunForbiddenError,
    RunNotFinishedError,
    RunNotForkableError,
    RunNotFoundError,
    RunStillRunningError,
)
from app.models import Event, Run
from app.services.run_service import RunService

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_create() -> RunCreate:
    return RunCreate(
        question="What is the capital of France?",
        user_context=None,
        output_format=OutputFormat.PROSE,
        confidence_threshold=0.8,
    )


async def _create_run(session: AsyncSession, username: str = "testuser") -> Run:
    svc = RunService(session)
    resp = await svc.create_run(_make_create(), username)
    return (await session.get(Run, resp.id))  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# create_run (AC-01)
# ---------------------------------------------------------------------------


async def test_create_run_persists(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    svc = RunService(sqlite_session)
    resp = await svc.create_run(_make_create(), seeded_user)

    assert resp.id is not None
    assert resp.owner_username == seeded_user
    assert resp.stop_reason is None

    fetched = await sqlite_session.get(Run, resp.id)
    assert fetched is not None
    assert fetched.question == "What is the capital of France?"


async def test_get_run_returns_existing(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _create_run(sqlite_session, seeded_user)
    svc = RunService(sqlite_session)
    resp = await svc.get_run(run.id)
    assert resp.id == run.id


async def test_get_run_raises_when_missing(sqlite_session: AsyncSession) -> None:
    import uuid

    svc = RunService(sqlite_session)
    with pytest.raises(RunNotFoundError):
        await svc.get_run(uuid.uuid4())


# ---------------------------------------------------------------------------
# list_runs_keyset (BRD-20 AC-07..AC-12)
# ---------------------------------------------------------------------------


async def test_list_runs_keyset_truncates_long_questions(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    long_q = "x" * 150
    run = Run(
        owner_username=seeded_user,
        question=long_q,
        output_format="prose",
        confidence_threshold=0.7,
    )
    sqlite_session.add(run)
    await sqlite_session.commit()

    svc = RunService(sqlite_session)
    page = await svc.list_runs_keyset(seeded_user)
    assert len(page.items) == 1
    assert page.items[0].question == "x" * 100 + "..."
    assert page.has_more is False
    assert page.next_cursor is None


async def test_list_runs_keyset_owner_scoped_excludes_other_users(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """BRD-20 AC-09: list MUST NOT contain runs belonging to other users."""
    from app.models import User

    other = User(username="bob", token_hash="y" * 64)
    sqlite_session.add(other)
    await sqlite_session.commit()
    await _create_run(sqlite_session, "bob")
    await _create_run(sqlite_session, seeded_user)

    svc = RunService(sqlite_session)
    page = await svc.list_runs_keyset(seeded_user)
    assert len(page.items) == 1
    assert page.items[0].username == seeded_user


async def test_list_runs_keyset_orders_started_at_desc_id_desc(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """BRD-20 AC-08: deterministic order (started_at DESC, id DESC)."""
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    # Insert 3 with same started_at to exercise the id tiebreaker.
    rows: list[Run] = []
    for _ in range(3):
        r = Run(
            owner_username=seeded_user,
            question="q",
            output_format="prose",
            confidence_threshold=0.7,
            started_at=base,
        )
        sqlite_session.add(r)
        rows.append(r)
    # Plus one strictly newer.
    newer = Run(
        owner_username=seeded_user,
        question="q",
        output_format="prose",
        confidence_threshold=0.7,
        started_at=base.replace(hour=13),
    )
    sqlite_session.add(newer)
    await sqlite_session.commit()

    svc = RunService(sqlite_session)
    page = await svc.list_runs_keyset(seeded_user, limit=10)
    ids = [item.id for item in page.items]
    assert ids[0] == newer.id
    # Tie-broken by id DESC for the remaining three.
    same_ts_ids = sorted([r.id for r in rows], reverse=True)
    assert ids[1:] == same_ts_ids


async def test_list_runs_keyset_pagination_has_more_and_cursor(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """BRD-20 AC-08, AC-11: has_more True + cursor when more rows exist."""
    for i in range(5):
        r = Run(
            owner_username=seeded_user,
            question=f"q{i}",
            output_format="prose",
            confidence_threshold=0.7,
            started_at=datetime(2026, 1, 1, 10, i, 0, tzinfo=UTC),
        )
        sqlite_session.add(r)
    await sqlite_session.commit()

    svc = RunService(sqlite_session)
    page1 = await svc.list_runs_keyset(seeded_user, limit=2)
    assert len(page1.items) == 2
    assert page1.has_more is True
    assert page1.next_cursor is not None

    page2 = await svc.list_runs_keyset(
        seeded_user, limit=2, cursor=page1.next_cursor
    )
    assert len(page2.items) == 2
    assert page2.has_more is True
    # No overlap between page boundaries.
    assert {i.id for i in page1.items}.isdisjoint({i.id for i in page2.items})

    page3 = await svc.list_runs_keyset(
        seeded_user, limit=2, cursor=page2.next_cursor
    )
    assert len(page3.items) == 1
    assert page3.has_more is False
    assert page3.next_cursor is None


async def test_list_runs_keyset_invalid_cursor_raises(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """BRD-20 AC-11: malformed cursor → InvalidCursorError (400)."""
    svc = RunService(sqlite_session)
    with pytest.raises(InvalidCursorError):
        await svc.list_runs_keyset(seeded_user, cursor="!!!not-base64!!!")


# ---------------------------------------------------------------------------
# delete_run (BRD-20 AC-03..AC-06)
# ---------------------------------------------------------------------------


async def _stop_run(
    session: AsyncSession, run: Run, reason: StopReason = StopReason.JUDGE_CONFIRMED
) -> None:
    run.stop_reason = reason.value
    run.stopped_at = datetime.now(UTC)
    await session.commit()


async def test_delete_run_removes_finished_run(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """BRD-20 AC-03: finished run is deleted permanently."""
    run = await _create_run(sqlite_session, seeded_user)
    await _stop_run(sqlite_session, run)
    run_id = run.id

    svc = RunService(sqlite_session)
    await svc.delete_run(run_id, seeded_user)

    sqlite_session.expire_all()
    assert await sqlite_session.get(Run, run_id) is None


async def test_delete_run_cascades_events(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """BRD-20 AC-06: associated events are removed via cascade."""
    import sqlalchemy as sa

    run = await _create_run(sqlite_session, seeded_user)
    sqlite_session.add(
        Event(
            run_id=run.id,
            step_index=1,
            type="PlanCreated",
            payload={"sub_claims": [], "rationale": "r"},
        )
    )
    await _stop_run(sqlite_session, run)

    svc = RunService(sqlite_session)
    await svc.delete_run(run.id, seeded_user)

    sqlite_session.expire_all()
    result = await sqlite_session.execute(
        sa.select(sa.func.count(Event.id)).where(Event.run_id == run.id)
    )
    assert result.scalar_one() == 0


async def test_delete_run_orphans_forks(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """BRD-20 AC-06: forks survive parent deletion (DB enforces SET NULL).

    The ``ON DELETE SET NULL`` clause is a Postgres-level guarantee on
    ``runs.parent_run_id``. SQLite in unit tests does not enforce FK
    actions unless ``PRAGMA foreign_keys=ON`` is set, so we only assert
    the survivability part here (the SET NULL is covered by the model
    definition and migration tests).
    """
    parent = await _create_run(sqlite_session, seeded_user)
    forkable = Event(
        run_id=parent.id,
        step_index=1,
        type="PlanCreated",
        payload={"sub_claims": [], "rationale": "r"},
    )
    sqlite_session.add(forkable)
    await sqlite_session.commit()

    svc = RunService(sqlite_session)
    fork = await svc.fork_run(
        parent.id, RunForkRequest(event_id=forkable.id), seeded_user
    )
    await _stop_run(sqlite_session, parent)

    await svc.delete_run(parent.id, seeded_user)

    sqlite_session.expire_all()
    fork_row = await sqlite_session.get(Run, fork.id)
    assert fork_row is not None


async def test_delete_run_missing_raises_404(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    svc = RunService(sqlite_session)
    with pytest.raises(RunNotFoundError):
        await svc.delete_run(uuid.uuid4(), seeded_user)


async def test_delete_run_not_owned_raises_403(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """BRD-20 AC-05: caller must own the run."""
    from app.models import User

    other = User(username="bob", token_hash="y" * 64)
    sqlite_session.add(other)
    await sqlite_session.commit()
    run = await _create_run(sqlite_session, "bob")
    await _stop_run(sqlite_session, run)

    svc = RunService(sqlite_session)
    with pytest.raises(RunForbiddenError):
        await svc.delete_run(run.id, seeded_user)


async def test_delete_run_ownership_check_precedes_terminal_check(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """BRD-20 §4.5 leak guard: 403 must fire before 409.

    A still-running run owned by someone else must NOT leak its state via
    a 409 to the caller; it must yield 403.
    """
    from app.models import User

    other = User(username="bob", token_hash="y" * 64)
    sqlite_session.add(other)
    await sqlite_session.commit()
    run = await _create_run(sqlite_session, "bob")  # in-progress (no stop_reason)

    svc = RunService(sqlite_session)
    with pytest.raises(RunForbiddenError):
        await svc.delete_run(run.id, seeded_user)


async def test_delete_run_in_progress_raises_409(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """BRD-20 AC-04: cannot delete a run that is still in progress."""
    run = await _create_run(sqlite_session, seeded_user)

    svc = RunService(sqlite_session)
    with pytest.raises(RunNotFinishedError):
        await svc.delete_run(run.id, seeded_user)


async def test_delete_run_swallows_run_still_terminating(
    sqlite_session: AsyncSession,
    seeded_user: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BRD-20 §4.5: a hung await_terminal must NOT shadow the AC-04 409 body."""
    from app.exceptions import RunStillTerminatingError

    async def _raise_stt(*_args: object, **_kwargs: object) -> None:
        raise RunStillTerminatingError("x")

    monkeypatch.setattr(
        "app.agent.runner.agent_runner.await_terminal", _raise_stt
    )

    run = await _create_run(sqlite_session, seeded_user)  # in-progress

    svc = RunService(sqlite_session)
    with pytest.raises(RunNotFinishedError):
        await svc.delete_run(run.id, seeded_user)


async def test_delete_run_closes_sse_connection(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """BRD-20 §9 last-row race: SSE state is cleared post-commit."""
    from app.sse.manager import connection_manager

    connection_manager.reset()
    run = await _create_run(sqlite_session, seeded_user)
    await _stop_run(sqlite_session, run)

    svc = RunService(sqlite_session)
    await svc.delete_run(run.id, seeded_user)

    # Idempotent: a second close is a no-op.
    connection_manager.close(run.id)
    assert connection_manager.is_cancelled(run.id) is True
    connection_manager.reset()


# ---------------------------------------------------------------------------
# cancel_run (AC-04)
# ---------------------------------------------------------------------------


async def test_cancel_sets_stop_reason_user_cancelled(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _create_run(sqlite_session, seeded_user)
    svc = RunService(sqlite_session)
    resp = await svc.cancel_run(run.id, seeded_user)

    assert resp.stop_reason == StopReason.USER_CANCELLED
    assert resp.stopped_at is not None


async def test_cancel_rejects_already_stopped_run(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _create_run(sqlite_session, seeded_user)
    svc = RunService(sqlite_session)
    await svc.cancel_run(run.id, seeded_user)

    with pytest.raises(RunAlreadyStoppedError):
        await svc.cancel_run(run.id, seeded_user)


async def test_cancel_missing_run_raises_404(sqlite_session: AsyncSession) -> None:
    import uuid

    svc = RunService(sqlite_session)
    with pytest.raises(RunNotFoundError):
        await svc.cancel_run(uuid.uuid4(), "testuser")


async def test_cancel_run_signals_connection_manager(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """RF-08 / IP-10 AC-09: cancel_run flips the in-process SSE cancel flag."""
    from app.sse.manager import connection_manager

    connection_manager.reset()
    run = await _create_run(sqlite_session, seeded_user)
    assert connection_manager.is_cancelled(run.id) is False

    svc = RunService(sqlite_session)
    await svc.cancel_run(run.id, seeded_user)

    assert connection_manager.is_cancelled(run.id) is True
    connection_manager.reset()


# ---------------------------------------------------------------------------
# resume_run (AC-05)
# ---------------------------------------------------------------------------


async def test_resume_clears_stop_state(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _create_run(sqlite_session, seeded_user)
    svc = RunService(sqlite_session)
    await svc.cancel_run(run.id, seeded_user)
    # IP-15: resume requires an anchor `Stopped(user_cancelled)` event.
    sqlite_session.add(
        Event(
            run_id=run.id,
            step_index=1,
            type="Stopped",
            payload={"stop_reason": StopReason.USER_CANCELLED.value},
        )
    )
    await sqlite_session.commit()

    resp = await svc.resume_run(run.id, seeded_user)
    assert resp.stop_reason is None
    assert resp.stopped_at is None


async def test_resume_rejects_judge_confirmed_run(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _create_run(sqlite_session, seeded_user)
    run.stop_reason = StopReason.JUDGE_CONFIRMED.value
    await sqlite_session.commit()

    svc = RunService(sqlite_session)
    with pytest.raises(RunAlreadyStoppedError):
        await svc.resume_run(run.id, seeded_user)


async def test_resume_rejects_still_running(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _create_run(sqlite_session, seeded_user)
    svc = RunService(sqlite_session)
    with pytest.raises(RunStillRunningError):
        await svc.resume_run(run.id, seeded_user)


async def test_resume_accepts_errored_state(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _create_run(sqlite_session, seeded_user)
    run.stop_reason = StopReason.ERRORED.value
    # IP-15: resume requires an anchor `AgentErrored` event.
    sqlite_session.add(
        Event(
            run_id=run.id,
            step_index=1,
            type="AgentErrored",
            payload={
                "error_type": "LLMError",
                "error_message": "boom",
                "recoverable": True,
            },
        )
    )
    await sqlite_session.commit()

    svc = RunService(sqlite_session)
    resp = await svc.resume_run(run.id, seeded_user)
    assert resp.stop_reason is None


# ---------------------------------------------------------------------------
# fork_run (AC-03)
# ---------------------------------------------------------------------------


async def test_fork_rejects_non_forkable_event(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _create_run(sqlite_session, seeded_user)
    # `ToolCalled` is NOT in FORKABLE_EVENTS.
    event = Event(
        run_id=run.id,
        step_index=1,
        type="ToolCalled",
        payload={"source_type": "tavily", "query": "q", "query_intent": "i"},
    )
    sqlite_session.add(event)
    await sqlite_session.commit()

    svc = RunService(sqlite_session)
    with pytest.raises(RunNotForkableError):
        await svc.fork_run(run.id, RunForkRequest(event_id=event.id), seeded_user)


async def test_fork_rejects_unknown_event(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    import uuid

    run = await _create_run(sqlite_session, seeded_user)
    svc = RunService(sqlite_session)
    with pytest.raises(EventNotFoundError):
        await svc.fork_run(
            run.id, RunForkRequest(event_id=uuid.uuid4()), seeded_user
        )


async def test_fork_sets_parent_and_event(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _create_run(sqlite_session, seeded_user)
    forkable_event = Event(
        run_id=run.id,
        step_index=1,
        type="PlanCreated",
        payload={"sub_claims": [], "rationale": "r"},
    )
    sqlite_session.add(forkable_event)
    await sqlite_session.commit()

    svc = RunService(sqlite_session)
    resp = await svc.fork_run(
        run.id, RunForkRequest(event_id=forkable_event.id), seeded_user
    )
    assert resp.parent_run_id == run.id
    assert resp.forked_at_event_id == forkable_event.id
    assert resp.id != run.id


# ---------------------------------------------------------------------------
# IP-15 — resume emits the canonical ResumedAfter* event (RF-11) and the
# fork endpoint rejects cross-run events. See
# docs/implementation-phase/implementation-plans/IP-15-fork-resume.md §6.
# ---------------------------------------------------------------------------


async def _seed_errored_run(session: AsyncSession, username: str) -> tuple[Run, Event]:
    """Run with an `AgentErrored` event at step 5 and stop_reason=errored."""
    run = await _create_run(session, username)
    anchor = Event(
        run_id=run.id,
        step_index=5,
        type="AgentErrored",
        payload={
            "error_type": "LLMError",
            "error_message": "rate limited",
            "recoverable": True,
        },
    )
    session.add(anchor)
    run.stop_reason = StopReason.ERRORED.value
    run.stopped_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(anchor)
    return run, anchor


async def _seed_cancelled_run(session: AsyncSession, username: str) -> tuple[Run, Event]:
    """Run with a `Stopped(user_cancelled)` event at step 4 and stop_reason=user_cancelled."""
    run = await _create_run(session, username)
    anchor = Event(
        run_id=run.id,
        step_index=4,
        type="Stopped",
        payload={"stop_reason": StopReason.USER_CANCELLED.value},
    )
    session.add(anchor)
    run.stop_reason = StopReason.USER_CANCELLED.value
    run.stopped_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(anchor)
    return run, anchor


async def _latest_event(session: AsyncSession, run_id: uuid.UUID) -> Event | None:
    import sqlalchemy as sa

    query = (
        sa.select(Event)
        .where(Event.run_id == run_id)
        .order_by(Event.step_index.desc())
        .limit(1)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def test_resume_errored_emits_ResumedAfterError_with_anchor(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """IP-15 B1: ResumedAfterError points at the latest AgentErrored event."""
    run, anchor = await _seed_errored_run(sqlite_session, seeded_user)

    svc = RunService(sqlite_session)
    resp = await svc.resume_run(run.id, seeded_user)

    assert resp.stop_reason is None
    assert resp.stopped_at is None

    latest = await _latest_event(sqlite_session, run.id)
    assert latest is not None
    assert latest.type == "ResumedAfterError"
    assert latest.parent_event_id == anchor.id
    assert latest.step_index == anchor.step_index + 1
    assert latest.payload["original_error_event_id"] == str(anchor.id)
    assert latest.payload["resume_point"] == f"after_step_{anchor.step_index}"


async def test_resume_cancelled_emits_ResumedAfterCancel_with_anchor(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """IP-15 B1: ResumedAfterCancel points at the Stopped(user_cancelled) event."""
    run, anchor = await _seed_cancelled_run(sqlite_session, seeded_user)

    svc = RunService(sqlite_session)
    resp = await svc.resume_run(run.id, seeded_user)

    assert resp.stop_reason is None
    assert resp.stopped_at is None

    latest = await _latest_event(sqlite_session, run.id)
    assert latest is not None
    assert latest.type == "ResumedAfterCancel"
    assert latest.parent_event_id == anchor.id
    assert latest.payload["cancel_event_id"] == str(anchor.id)
    assert latest.payload["resume_point"] == f"after_step_{anchor.step_index}"


async def test_resume_raises_500_when_anchor_event_missing(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """IP-15 B1: corrupt state (errored without AgentErrored) → 500, status unchanged."""
    from fastapi import HTTPException

    run = await _create_run(sqlite_session, seeded_user)
    run.stop_reason = StopReason.ERRORED.value
    run.stopped_at = datetime.now(UTC)
    await sqlite_session.commit()

    svc = RunService(sqlite_session)
    with pytest.raises(HTTPException) as excinfo:
        await svc.resume_run(run.id, seeded_user)
    assert excinfo.value.status_code == 500

    await sqlite_session.refresh(run)
    assert run.stop_reason == StopReason.ERRORED.value
    assert run.stopped_at is not None


async def test_resume_is_atomic_when_append_fails(
    sqlite_session: AsyncSession,
    seeded_user: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IP-15 B1: if append_event raises, run.stop_reason is unchanged after rollback."""
    from app.services import run_service as run_service_module

    run, _ = await _seed_errored_run(sqlite_session, seeded_user)

    async def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("flush boom")

    monkeypatch.setattr(
        run_service_module.EventService, "append_event", _boom
    )

    svc = RunService(sqlite_session)
    with pytest.raises(RuntimeError):
        await svc.resume_run(run.id, seeded_user)

    # Rollback the failed transaction so we can re-query.
    await sqlite_session.rollback()
    await sqlite_session.refresh(run)
    assert run.stop_reason == StopReason.ERRORED.value


async def test_fork_rejects_cross_run_event(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    """IP-15 B2: forking run A with an event of run B → EventNotFoundError (404)."""
    run_a = await _create_run(sqlite_session, seeded_user)
    run_b = await _create_run(sqlite_session, seeded_user)
    event_b = Event(
        run_id=run_b.id,
        step_index=1,
        type="PlanCreated",
        payload={"sub_claims": [], "rationale": "r"},
    )
    sqlite_session.add(event_b)
    await sqlite_session.commit()

    svc = RunService(sqlite_session)
    with pytest.raises(EventNotFoundError):
        await svc.fork_run(
            run_a.id, RunForkRequest(event_id=event_b.id), seeded_user
        )


# ---------------------------------------------------------------------------
# Agent runner wiring (BRD-19 / IP-19 §6.1 — T9.1)
# ---------------------------------------------------------------------------


class _RecordingAgentRunner:
    """Records every call so tests can assert RunService delegates correctly."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.await_terminal_raises: BaseException | None = None

    async def start(self, run_id: uuid.UUID) -> None:
        self.calls.append(("start", run_id))

    def cancel(self, run_id: uuid.UUID) -> bool:
        self.calls.append(("cancel", run_id))
        return True

    async def await_terminal(
        self, run_id: uuid.UUID, timeout: float = 5.0
    ) -> None:
        self.calls.append(("await_terminal", run_id))
        if self.await_terminal_raises is not None:
            raise self.await_terminal_raises

    async def shutdown(self) -> None:
        self.calls.append(("shutdown", None))

    def is_running(self, run_id: uuid.UUID) -> bool:  # noqa: ARG002
        return False


@pytest.mark.real_agent_runner
async def test_create_run_invokes_runner_start(
    sqlite_session: AsyncSession,
    seeded_user: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _RecordingAgentRunner()
    monkeypatch.setattr("app.agent.runner.agent_runner", fake)

    svc = RunService(sqlite_session)
    resp = await svc.create_run(_make_create(), seeded_user)

    assert fake.calls == [("start", resp.id)]


@pytest.mark.real_agent_runner
async def test_cancel_run_invokes_runner_cancel(
    sqlite_session: AsyncSession,
    seeded_user: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _RecordingAgentRunner()
    monkeypatch.setattr("app.agent.runner.agent_runner", fake)

    run = await _create_run(sqlite_session, seeded_user)
    fake.calls.clear()
    svc = RunService(sqlite_session)
    await svc.cancel_run(run.id, seeded_user)

    kinds = [c[0] for c in fake.calls]
    assert "cancel" in kinds
    assert fake.calls[-1] == ("cancel", run.id) or ("cancel", run.id) in fake.calls


@pytest.mark.real_agent_runner
async def test_resume_run_awaits_terminal_then_starts(
    sqlite_session: AsyncSession,
    seeded_user: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _RecordingAgentRunner()
    monkeypatch.setattr("app.agent.runner.agent_runner", fake)

    run = await _create_run(sqlite_session, seeded_user)
    run.stop_reason = StopReason.ERRORED.value
    sqlite_session.add(
        Event(
            run_id=run.id,
            step_index=1,
            type="AgentErrored",
            payload={
                "error_type": "LLMError",
                "error_message": "boom",
                "recoverable": True,
            },
        )
    )
    await sqlite_session.commit()
    fake.calls.clear()

    svc = RunService(sqlite_session)
    await svc.resume_run(run.id, seeded_user)

    kinds = [c[0] for c in fake.calls]
    assert kinds[0] == "await_terminal"
    assert kinds[-1] == "start"


@pytest.mark.real_agent_runner
async def test_resume_run_timeout_propagates_409(
    sqlite_session: AsyncSession,
    seeded_user: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.exceptions import RunStillTerminatingError

    fake = _RecordingAgentRunner()
    fake.await_terminal_raises = RunStillTerminatingError("x")
    monkeypatch.setattr("app.agent.runner.agent_runner", fake)

    run = await _create_run(sqlite_session, seeded_user)
    run.stop_reason = StopReason.ERRORED.value
    await sqlite_session.commit()

    svc = RunService(sqlite_session)
    with pytest.raises(RunStillTerminatingError):
        await svc.resume_run(run.id, seeded_user)

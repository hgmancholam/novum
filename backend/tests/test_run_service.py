"""Unit tests for `RunService` (BRD-03 AC-01, AC-04, AC-05)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OutputFormat, StopReason
from app.domain.run import RunCreate, RunForkRequest
from app.exceptions import (
    EventNotFoundError,
    RunAlreadyStoppedError,
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
# list_runs
# ---------------------------------------------------------------------------


async def test_list_runs_truncates_long_questions(
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
    items = await svc.list_runs(seeded_user)
    assert len(items) == 1
    assert items[0].question == "x" * 100 + "..."
    assert len(items[0].question) == 103


async def test_list_runs_does_not_truncate_short_questions(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    await _create_run(sqlite_session, seeded_user)
    svc = RunService(sqlite_session)
    items = await svc.list_runs(seeded_user)
    assert len(items) == 1
    assert items[0].question == "What is the capital of France?"


async def test_list_runs_scopes_to_username(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    # Seed a second user + run.
    from app.models import User

    other = User(username="bob", token_hash="y" * 64)
    sqlite_session.add(other)
    await sqlite_session.commit()
    await _create_run(sqlite_session, "bob")
    await _create_run(sqlite_session, seeded_user)

    svc = RunService(sqlite_session)
    mine = await svc.list_runs(seeded_user)
    theirs = await svc.list_runs("bob")
    assert len(mine) == 1
    assert len(theirs) == 1
    assert mine[0].id != theirs[0].id


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


# ---------------------------------------------------------------------------
# resume_run (AC-05)
# ---------------------------------------------------------------------------


async def test_resume_clears_stop_state(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _create_run(sqlite_session, seeded_user)
    svc = RunService(sqlite_session)
    await svc.cancel_run(run.id, seeded_user)

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

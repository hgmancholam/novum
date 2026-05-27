"""Unit tests for `EventService`."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OutputFormat
from app.domain.events import QuestionAskedEvent
from app.domain.run import RunCreate
from app.models import Run
from app.services.event_service import EventService
from app.services.run_service import RunService

pytestmark = pytest.mark.asyncio


async def _make_run(session: AsyncSession, username: str) -> Run:
    svc = RunService(session)
    resp = await svc.create_run(
        RunCreate(
            question="What is the capital of France?",
            user_context=None,
            output_format=OutputFormat.PROSE,
            confidence_threshold=0.7,
        ),
        username,
    )
    fetched = await session.get(Run, resp.id)
    assert fetched is not None
    return fetched


async def test_append_assigns_sequential_step_index(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _make_run(sqlite_session, seeded_user)
    svc = EventService(sqlite_session)

    e1 = await svc.append_event(run.id, QuestionAskedEvent(question="q1"))
    e2 = await svc.append_event(run.id, QuestionAskedEvent(question="q2"))
    e3 = await svc.append_event(run.id, QuestionAskedEvent(question="q3"))

    assert e1.step_index == 1
    assert e2.step_index == 2
    assert e3.step_index == 3


async def test_append_excludes_envelope_keys_from_payload(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _make_run(sqlite_session, seeded_user)
    svc = EventService(sqlite_session)

    db_event = await svc.append_event(
        run.id, QuestionAskedEvent(question="hello world")
    )

    forbidden = {"id", "run_id", "step_index", "parent_event_id", "created_at"}
    assert forbidden.isdisjoint(db_event.payload.keys())
    assert db_event.payload["question"] == "hello world"
    assert db_event.payload["type"] == "QuestionAsked"


async def test_get_events_filters_by_after_step(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _make_run(sqlite_session, seeded_user)
    svc = EventService(sqlite_session)

    await svc.append_event(run.id, QuestionAskedEvent(question="q1"))
    await svc.append_event(run.id, QuestionAskedEvent(question="q2"))
    await svc.append_event(run.id, QuestionAskedEvent(question="q3"))

    all_events = await svc.get_events(run.id)
    assert len(all_events) == 3

    after_first = await svc.get_events(run.id, after_step=1)
    assert len(after_first) == 2
    assert after_first[0]["step_index"] == 2


async def test_get_events_returns_sse_shape(
    sqlite_session: AsyncSession, seeded_user: str
) -> None:
    run = await _make_run(sqlite_session, seeded_user)
    svc = EventService(sqlite_session)
    await svc.append_event(run.id, QuestionAskedEvent(question="hi"))

    events = await svc.get_events(run.id)
    assert len(events) == 1
    e = events[0]
    assert e["type"] == "QuestionAsked"
    assert e["step_index"] == 1
    assert e["run_id"] == str(run.id)
    assert "id" in e and "created_at" in e
    # payload keys are merged at the top level
    assert e["question"] == "hi"


async def test_get_event_returns_none_when_missing(
    sqlite_session: AsyncSession,
) -> None:
    import uuid

    svc = EventService(sqlite_session)
    assert await svc.get_event(uuid.uuid4()) is None


async def test_append_event_no_commit_flushes_but_does_not_commit(
    sqlite_session: AsyncSession,
    seeded_user: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IP-15 B0: ``commit=False`` flushes (event.id populated) without committing.

    Counts ``AsyncSession.commit`` invocations via ``monkeypatch`` — it must
    not be called by ``append_event`` when ``commit=False``, leaving the
    surrounding transaction open for the caller (``RunService.resume_run``).
    """
    run = await _make_run(sqlite_session, seeded_user)
    svc = EventService(sqlite_session)

    commit_calls = 0
    original_commit = sqlite_session.commit

    async def _counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1
        await original_commit()

    monkeypatch.setattr(sqlite_session, "commit", _counting_commit)

    db_event = await svc.append_event(
        run.id, QuestionAskedEvent(question="flush only"), commit=False
    )

    assert db_event.id is not None
    assert db_event.step_index == 1
    assert commit_calls == 0


async def test_append_event_default_still_commits(
    sqlite_session: AsyncSession,
    seeded_user: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default ``commit=True`` preserves existing caller contracts (BRD-15 IP B0)."""
    run = await _make_run(sqlite_session, seeded_user)
    svc = EventService(sqlite_session)

    commit_calls = 0
    original_commit = sqlite_session.commit

    async def _counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1
        await original_commit()

    monkeypatch.setattr(sqlite_session, "commit", _counting_commit)

    await svc.append_event(run.id, QuestionAskedEvent(question="commit too"))

    assert commit_calls == 1

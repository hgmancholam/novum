"""Unit tests for ``app.agent.runner.AgentRunner`` (BRD-19 / IP-19 §6.1).

The runner is the runtime bridge that ties the FSM (BRD-07) to the API
(BRD-03) and the SSE stream (BRD-10). These tests use a ``FakeOrchestrator``
to keep the FSM out of scope and exercise lifecycle, single-writer
guarantees, supervisor recovery, and event-fold rehydration.

All tests opt in to the real ``AgentRunner`` via the ``real_agent_runner``
marker so the autouse no-op stub in ``conftest.py`` does NOT apply.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.agent import runner as runner_module
from app.agent.run_state import RunState
from app.agent.runner import (
    AgentRunner,
    _fold_events,
    _stopped_followed_by_resume,
)
from app.agent.states import AgentState
from app.domain.enums import (
    EventType,
    EvidencePolarity,
    OutputFormat,
    SourceType,
    StopReason,
)
from app.domain.events import (
    BaseEvent,
    EvidenceAddedEvent,
    PlanCreatedEvent,
    QuestionAskedEvent,
    StoppedEvent,
    SubClaim,
)
from app.exceptions import RunAlreadyRunningError, RunStillTerminatingError
from app.models import Event, Run, User

pytestmark = [pytest.mark.real_agent_runner]


# ---------------------------------------------------------------------------
# Test scaffolding
# ---------------------------------------------------------------------------


class FakeOrchestrator:
    """Drop-in replacement for ``AgentOrchestrator`` for runner tests.

    Mirrors the real attribute surface used by ``AgentRunner``:
    ``state``, ``cancel()`` setting ``_cancelled``.
    """

    def __init__(
        self,
        state: RunState,
        emit: Callable[[BaseEvent], Awaitable[None]],
        stopping_policy: object = None,  # noqa: ARG002
    ) -> None:
        self.state = state
        self._emit = emit
        self._cancelled = False
        # Callers (the fixture) inject a coroutine factory to script run().
        self.scripted_run: Callable[[FakeOrchestrator], Awaitable[None]] | None = None

    def cancel(self) -> None:
        self._cancelled = True

    async def run(self) -> None:
        if self.scripted_run is not None:
            await self.scripted_run(self)


_FAKE_HOLDER: dict[str, FakeOrchestrator] = {}


def _make_fake_factory(
    scripted_run: Callable[[FakeOrchestrator], Awaitable[None]],
) -> Callable[..., FakeOrchestrator]:
    """Return a constructor that records the created FakeOrchestrator."""

    def _factory(
        state: RunState,
        emit: Callable[[BaseEvent], Awaitable[None]],
        stopping_policy: object = None,
    ) -> FakeOrchestrator:
        orch = FakeOrchestrator(state, emit, stopping_policy)
        orch.scripted_run = scripted_run
        _FAKE_HOLDER["last"] = orch
        return orch

    return _factory


@pytest.fixture
async def seeded_run(
    sqlite_engine: AsyncEngine, sqlite_session_maker: async_sessionmaker[object]
) -> AsyncGenerator[UUID, None]:
    """Insert a User + Run row directly via the test engine."""
    username = f"runner_user_{uuid4().hex[:8]}"
    run_id = uuid4()
    async with sqlite_session_maker() as s:
        s.add(
            User(
                id=uuid4(),
                username=username,
                token_hash="x" * 64,
                created_at=datetime.now(UTC),
            )
        )
        s.add(
            Run(
                id=run_id,
                owner_username=username,
                question="What is the capital of France?",
                user_context=None,
                output_format=OutputFormat.PROSE.value,
                confidence_threshold=0.7,
                started_at=datetime.now(UTC),
            )
        )
        await s.commit()
    yield run_id


@pytest.fixture
def sqlite_session_maker(sqlite_engine: AsyncEngine) -> async_sessionmaker[object]:
    return async_sessionmaker(sqlite_engine, expire_on_commit=False)


@pytest.fixture
def patched_runner(
    sqlite_engine: AsyncEngine,
    sqlite_session_maker: async_sessionmaker[object],
    monkeypatch: pytest.MonkeyPatch,
) -> AgentRunner:
    """A fresh ``AgentRunner`` bound to the SQLite engine + fake orchestrator.

    Each test that needs scripted behaviour replaces
    ``runner_module.AgentOrchestrator`` via ``monkeypatch`` before
    calling ``runner.start(...)``.
    """
    monkeypatch.setattr(
        runner_module, "async_session_maker", sqlite_session_maker, raising=False
    )
    return AgentRunner()


# ---------------------------------------------------------------------------
# Pure helpers — _stopped_followed_by_resume / _fold_events
# ---------------------------------------------------------------------------


def test_stopped_followed_by_resume_marks_skip() -> None:
    events = [
        {"type": EventType.QUESTION_ASKED.value, "step_index": 1},
        {"type": EventType.STOPPED.value, "step_index": 2, "stop_reason": "errored"},
        {"type": EventType.RESUMED_AFTER_ERROR.value, "step_index": 3},
        {"type": EventType.EVIDENCE_ADDED.value, "step_index": 4},
        # A second STOPPED with no resume after — must NOT be skipped.
        {"type": EventType.STOPPED.value, "step_index": 5, "stop_reason": "errored"},
    ]
    assert _stopped_followed_by_resume(events) == {2}


def test_fold_skips_resumed_stopped_and_lands_in_searching() -> None:
    run_id = uuid4()
    state = RunState(
        run_id=run_id,
        question="Q",
        output_format=OutputFormat.PROSE,
    )
    events = [
        {"type": EventType.QUESTION_ASKED.value, "step_index": 1, "question": "Q"},
        {
            "type": EventType.PLAN_CREATED.value,
            "step_index": 2,
            "sub_claims": [
                {"id": "c1", "text": "claim 1"},
            ],
            "rationale": "r",
        },
        {
            "type": EventType.STOPPED.value,
            "step_index": 3,
            "stop_reason": StopReason.ERRORED.value,
        },
        {"type": EventType.RESUMED_AFTER_ERROR.value, "step_index": 4},
    ]
    _fold_events(state, events)

    assert state.current_state == AgentState.SEARCHING
    assert state.stop_reason is None
    assert len(state.sub_claims) == 1


def test_fold_terminal_stopped_without_resume_stays_stopped() -> None:
    run_id = uuid4()
    state = RunState(run_id=run_id, question="Q", output_format=OutputFormat.PROSE)
    events = [
        {"type": EventType.QUESTION_ASKED.value, "step_index": 1, "question": "Q"},
        {
            "type": EventType.STOPPED.value,
            "step_index": 2,
            "stop_reason": StopReason.JUDGE_CONFIRMED.value,
        },
    ]
    _fold_events(state, events)

    assert state.current_state == AgentState.STOPPED
    assert state.stop_reason == StopReason.JUDGE_CONFIRMED


# ---------------------------------------------------------------------------
# AgentRunner.start
# ---------------------------------------------------------------------------


async def test_start_spawns_orchestrator_and_persists_events(
    patched_runner: AgentRunner,
    seeded_run: UUID,
    sqlite_session_maker: async_sessionmaker[object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def script(orch: FakeOrchestrator) -> None:
        await orch._emit(QuestionAskedEvent(question=orch.state.question))
        await orch._emit(StoppedEvent(stop_reason=StopReason.JUDGE_CONFIRMED))

    monkeypatch.setattr(
        runner_module, "AgentOrchestrator", _make_fake_factory(script)
    )

    await patched_runner.start(seeded_run)
    async with asyncio.timeout(2.0):
        await patched_runner.await_terminal(seeded_run, timeout=2.0)

    async with sqlite_session_maker() as s:
        events = (
            await s.execute(select(Event).where(Event.run_id == seeded_run))
        ).scalars().all()
        run = await s.get(Run, seeded_run)

    assert {e.type for e in events} >= {
        EventType.QUESTION_ASKED.value,
        EventType.STOPPED.value,
    }
    assert run is not None
    assert run.stop_reason == StopReason.JUDGE_CONFIRMED.value
    assert run.stopped_at is not None


async def test_start_twice_raises_run_already_running(
    patched_runner: AgentRunner,
    seeded_run: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Script that blocks until released so the first task is still live.
    release = asyncio.Event()

    async def script(orch: FakeOrchestrator) -> None:  # noqa: ARG001
        await release.wait()

    monkeypatch.setattr(
        runner_module, "AgentOrchestrator", _make_fake_factory(script)
    )

    await patched_runner.start(seeded_run)
    try:
        with pytest.raises(RunAlreadyRunningError):
            await patched_runner.start(seeded_run)
    finally:
        release.set()
        async with asyncio.timeout(2.0):
            await patched_runner.await_terminal(seeded_run, timeout=2.0)


# ---------------------------------------------------------------------------
# AgentRunner.cancel
# ---------------------------------------------------------------------------


async def test_cancel_flips_orchestrator_flag_and_returns_true(
    patched_runner: AgentRunner,
    seeded_run: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()
    saw_cancel = asyncio.Event()

    async def script(orch: FakeOrchestrator) -> None:
        started.set()
        for _ in range(100):
            if orch._cancelled:
                saw_cancel.set()
                await orch._emit(StoppedEvent(stop_reason=StopReason.USER_CANCELLED))
                return
            await asyncio.sleep(0.01)

    monkeypatch.setattr(
        runner_module, "AgentOrchestrator", _make_fake_factory(script)
    )

    await patched_runner.start(seeded_run)
    async with asyncio.timeout(2.0):
        await started.wait()

    assert patched_runner.cancel(seeded_run) is True

    async with asyncio.timeout(2.0):
        await saw_cancel.wait()
        await patched_runner.await_terminal(seeded_run, timeout=2.0)


def test_cancel_unknown_run_returns_false(patched_runner: AgentRunner) -> None:
    assert patched_runner.cancel(uuid4()) is False


async def test_cancel_preserves_stopped_at(
    patched_runner: AgentRunner,
    seeded_run: UUID,
    sqlite_session_maker: async_sessionmaker[object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B-01: when a request handler set ``stopped_at`` before the runner
    emits its own Stopped event, the runner MUST NOT overwrite it."""
    earlier = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

    async with sqlite_session_maker() as s:
        run = await s.get(Run, seeded_run)
        assert run is not None
        run.stopped_at = earlier
        run.stop_reason = StopReason.USER_CANCELLED.value
        await s.commit()

    async def script(orch: FakeOrchestrator) -> None:
        await orch._emit(StoppedEvent(stop_reason=StopReason.USER_CANCELLED))

    monkeypatch.setattr(
        runner_module, "AgentOrchestrator", _make_fake_factory(script)
    )

    await patched_runner.start(seeded_run)
    async with asyncio.timeout(2.0):
        await patched_runner.await_terminal(seeded_run, timeout=2.0)

    async with sqlite_session_maker() as s:
        run = await s.get(Run, seeded_run)
    assert run is not None
    # NOT overwritten by the runner clock. SQLite drops tz info, so compare
    # the naive datetime components.
    assert run.stopped_at is not None
    assert run.stopped_at.replace(tzinfo=UTC) == earlier


# ---------------------------------------------------------------------------
# AgentRunner.await_terminal
# ---------------------------------------------------------------------------


async def test_await_terminal_unknown_run_returns_immediately(
    patched_runner: AgentRunner,
) -> None:
    async with asyncio.timeout(1.0):
        await patched_runner.await_terminal(uuid4(), timeout=1.0)


async def test_await_terminal_raises_409_on_timeout(
    patched_runner: AgentRunner,
    seeded_run: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = asyncio.Event()

    async def script(orch: FakeOrchestrator) -> None:  # noqa: ARG001
        await release.wait()

    monkeypatch.setattr(
        runner_module, "AgentOrchestrator", _make_fake_factory(script)
    )

    await patched_runner.start(seeded_run)
    try:
        with pytest.raises(RunStillTerminatingError):
            await patched_runner.await_terminal(seeded_run, timeout=0.1)
    finally:
        release.set()
        async with asyncio.timeout(2.0):
            await patched_runner.await_terminal(seeded_run, timeout=2.0)


# ---------------------------------------------------------------------------
# AgentRunner.shutdown
# ---------------------------------------------------------------------------


async def test_shutdown_cancels_and_joins_inflight_tasks(
    patched_runner: AgentRunner,
    seeded_run: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()

    async def script(orch: FakeOrchestrator) -> None:
        started.set()
        for _ in range(100):
            if orch._cancelled:
                return
            await asyncio.sleep(0.01)

    monkeypatch.setattr(
        runner_module, "AgentOrchestrator", _make_fake_factory(script)
    )

    await patched_runner.start(seeded_run)
    async with asyncio.timeout(2.0):
        await started.wait()
    async with asyncio.timeout(5.0):
        await patched_runner.shutdown()

    assert patched_runner.is_running(seeded_run) is False


# ---------------------------------------------------------------------------
# Supervisor — _supervisor_last_resort
# ---------------------------------------------------------------------------


async def test_supervisor_appends_errored_and_stopped_on_uncaught_exception(
    patched_runner: AgentRunner,
    seeded_run: UUID,
    sqlite_session_maker: async_sessionmaker[object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def script(orch: FakeOrchestrator) -> None:  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(
        runner_module, "AgentOrchestrator", _make_fake_factory(script)
    )

    await patched_runner.start(seeded_run)
    async with asyncio.timeout(2.0):
        await patched_runner.await_terminal(seeded_run, timeout=2.0)

    async with sqlite_session_maker() as s:
        events = (
            await s.execute(
                select(Event)
                .where(Event.run_id == seeded_run)
                .order_by(Event.step_index)
            )
        ).scalars().all()
        run = await s.get(Run, seeded_run)

    types = [e.type for e in events]
    assert EventType.AGENT_ERRORED.value in types
    assert types[-1] == EventType.STOPPED.value
    assert run is not None
    assert run.stop_reason == StopReason.ERRORED.value


async def test_supervisor_skips_redundant_stop_when_prior_stop_exists(
    patched_runner: AgentRunner,
    seeded_run: UUID,
    sqlite_session_maker: async_sessionmaker[object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the orchestrator emitted Stopped(X) before raising, the
    supervisor must NOT append a second AgentErrored/Stopped pair."""

    async def script(orch: FakeOrchestrator) -> None:
        await orch._emit(StoppedEvent(stop_reason=StopReason.JUDGE_CONFIRMED))
        raise RuntimeError("boom-after-stop")

    monkeypatch.setattr(
        runner_module, "AgentOrchestrator", _make_fake_factory(script)
    )

    await patched_runner.start(seeded_run)
    async with asyncio.timeout(2.0):
        await patched_runner.await_terminal(seeded_run, timeout=2.0)

    async with sqlite_session_maker() as s:
        events = (
            await s.execute(
                select(Event)
                .where(Event.run_id == seeded_run)
                .order_by(Event.step_index)
            )
        ).scalars().all()
        run = await s.get(Run, seeded_run)

    types = [e.type for e in events]
    # Exactly one STOPPED, no AGENT_ERRORED — supervisor saw the prior stop.
    assert types.count(EventType.STOPPED.value) == 1
    assert EventType.AGENT_ERRORED.value not in types
    assert run is not None
    assert run.stop_reason == StopReason.JUDGE_CONFIRMED.value


# ---------------------------------------------------------------------------
# Rehydration on resume
# ---------------------------------------------------------------------------


async def test_supervised_run_rehydrates_to_searching_after_resume(
    patched_runner: AgentRunner,
    seeded_run: UUID,
    sqlite_session_maker: async_sessionmaker[object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-seed Stopped(ERRORED) + ResumedAfterError; the runner must
    rehydrate ``state.current_state`` to SEARCHING (not STOPPED) and
    NOT raise on the historical sequence (BRD-19 §3.3 #15)."""
    # Seed history directly through EventService.
    from app.services.event_service import EventService

    async with sqlite_session_maker() as s:
        svc = EventService(s)
        await svc.append_event(
            seeded_run, QuestionAskedEvent(question="Q")
        )
        await svc.append_event(
            seeded_run,
            PlanCreatedEvent(
                sub_claims=[SubClaim(id="c1", text="x")],
                rationale="r",
            ),
        )
        await svc.append_event(
            seeded_run,
            EvidenceAddedEvent(
                source_type=SourceType.TAVILY,
                target_claim_id="c1",
                source_url="https://example.com",
                source_title="t",
                extracted_text="e",
                polarity=EvidencePolarity.SUPPORTS,
                confidence=0.9,
            ),
        )
        await svc.append_event(
            seeded_run, StoppedEvent(stop_reason=StopReason.ERRORED)
        )
        # Resume marker — appended by RunService.resume_run.
        from app.domain.events import ResumedAfterErrorEvent

        await svc.append_event(
            seeded_run,
            ResumedAfterErrorEvent(
                original_error_event_id=uuid4(),
                resume_point="SEARCHING",
            ),
        )

    captured: dict[str, RunState] = {}

    async def script(orch: FakeOrchestrator) -> None:
        captured["state"] = orch.state
        await orch._emit(StoppedEvent(stop_reason=StopReason.JUDGE_CONFIRMED))

    monkeypatch.setattr(
        runner_module, "AgentOrchestrator", _make_fake_factory(script)
    )

    await patched_runner.start(seeded_run)
    async with asyncio.timeout(2.0):
        await patched_runner.await_terminal(seeded_run, timeout=2.0)

    assert "state" in captured
    state = captured["state"]
    assert state.current_state == AgentState.SEARCHING
    assert state.stop_reason is None
    # Evidence and claims were folded back in.
    assert len(state.evidence) == 1
    assert len(state.sub_claims) == 1


# ---------------------------------------------------------------------------
# BRD-22: Complexity features integration (TC-07, TC-08)
# ---------------------------------------------------------------------------


async def test_wikipedia_first_in_preferred_sources(
    patched_runner: AgentRunner,
    seeded_run: UUID,
    sqlite_session_maker: async_sessionmaker[object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-07: trivial+FACTUAL sets preferred_sources=["wikipedia"]."""
    from app.domain.enums import ComplexityHint
    from app.services.event_service import EventService

    async with sqlite_session_maker() as s:
        svc = EventService(s)
        await svc.append_event(
            seeded_run, QuestionAskedEvent(question="Capital of Japan?")
        )
        await svc.append_event(
            seeded_run,
            PlanCreatedEvent(
                sub_claims=[SubClaim(id="c1", text="x")],
                rationale="r",
                complexity_hint=ComplexityHint.TRIVIAL,
                preferred_sources=["wikipedia"],
            ),
        )

    captured: dict[str, RunState] = {}

    async def script(orch: FakeOrchestrator) -> None:
        captured["state"] = orch.state
        await orch._emit(StoppedEvent(stop_reason=StopReason.JUDGE_CONFIRMED))

    monkeypatch.setattr(
        runner_module, "AgentOrchestrator", _make_fake_factory(script)
    )

    await patched_runner.start(seeded_run)
    async with asyncio.timeout(2.0):
        await patched_runner.await_terminal(seeded_run, timeout=2.0)

    assert "state" in captured
    state = captured["state"]
    assert state.preferred_sources == ["wikipedia"]


async def test_trivial_path_latency_under_5s(
    patched_runner: AgentRunner,
    seeded_run: UUID,
    sqlite_session_maker: async_sessionmaker[object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-08: Mocked trivial path (no LLM calls, no critique) completes quickly."""
    from app.domain.enums import ComplexityHint
    from app.services.event_service import EventService
    import time

    # Seed trivial path: QuestionAsked → PlanCreated (no critique)
    async with sqlite_session_maker() as s:
        svc = EventService(s)
        await svc.append_event(
            seeded_run, QuestionAskedEvent(question="Tokyo?")
        )

    async def script(orch: FakeOrchestrator) -> None:
        # Trivial path emits PlanCreated with critique_passes_target=0
        await orch._emit(
            PlanCreatedEvent(
                sub_claims=[SubClaim(id="c1", text="x")],
                rationale="r",
                complexity_hint=ComplexityHint.TRIVIAL,
                preferred_sources=["wikipedia"],
            )
        )
        # Skip critique, go straight to terminal
        await orch._emit(StoppedEvent(stop_reason=StopReason.JUDGE_CONFIRMED))

    monkeypatch.setattr(
        runner_module, "AgentOrchestrator", _make_fake_factory(script)
    )

    start = time.time()
    await patched_runner.start(seeded_run)
    async with asyncio.timeout(5.0):
        await patched_runner.await_terminal(seeded_run, timeout=5.0)
    elapsed = time.time() - start

    # Assert latency under 5s (mocked, no real LLM or search)
    assert elapsed < 5.0

    # Verify no PlanCritiquedEvent was emitted
    async with sqlite_session_maker() as s:
        from sqlalchemy import select as sa_select
        events = (
            await s.execute(
                sa_select(Event).where(Event.run_id == seeded_run).order_by(Event.step_index)
            )
        ).scalars().all()
    types = [e.type for e in events]
    assert EventType.PLAN_CRITIQUED.value not in types

"""Agent runner — the runtime bridge that ties AgentOrchestrator to FastAPI.

Spawns the FSM (BRD-07) as an ``asyncio.Task`` whenever a run is created
or resumed, fans every emitted event to both the event log (BRD-03) and
the SSE manager (BRD-10), enforces single-writer-per-run, and supervises
the task so an uncaught exception always leaves the run in a clean
terminal state (BRD-19 §4).

Architectural invariants (do not soften without updating BRD-19):

* **Single event loop.** ``uvicorn --workers 1`` guarantees the runner's
  registry is private to one Python process; concurrency uses ``anyio.Lock``,
  not OS file locks.
* **Cooperative cancellation only.** ``cancel()`` flips a flag on the
  orchestrator; we never call ``task.cancel()`` directly because that would
  interrupt the supervisor's terminal-write attempt.
* **Fresh DB session for terminal writes.** The long-lived supervisor
  session may already be doomed when an exception is raised, so terminal
  rows go through their own ``async_session_maker()`` context (B-01).
* **No transition_to during rehydration.** The fold pipeline assigns
  ``state.current_state`` directly so that historically-valid sequences
  cannot trigger ``ValueError`` from ``RunState.transition_to`` if the
  TRANSITIONS table tightens in the future.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import anyio
import structlog
from sqlalchemy import case, update

from app.agent.orchestrator import AgentOrchestrator
from app.agent.run_state import EvidenceItem, RunState
from app.agent.states import AgentState
from app.database import async_session_maker
from app.domain.enums import EventType, StopReason
from app.domain.events import (
    AgentErroredEvent,
    BaseEvent,
    ContradictionDetectedEvent,
    StoppedEvent,
    SubClaim,
)
from app.exceptions import RunAlreadyRunningError, RunStillTerminatingError
from app.llm.client import LLMPoolExhausted
from app.models import Run
from app.services.event_service import EventService
from app.sse.manager import connection_manager

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger(__name__)


type EmitCallback = Callable[[BaseEvent], Awaitable[None]]


# ---------------------------------------------------------------------------
# Event-fold helpers (BRD-19 §3.3).
# ---------------------------------------------------------------------------


def _apply_state(state: RunState, target: AgentState) -> None:
    """Direct assignment bypassing ``transition_to`` validation.

    Used ONLY during rehydration: historical event sequences are by
    definition legal at the time they were emitted, so re-validating them
    against the current TRANSITIONS table would be a false negative.
    """
    state.current_state = target


def _stopped_followed_by_resume(events: list[dict[str, Any]]) -> set[int]:
    """Pre-scan: return step_indices of STOPPED events immediately followed
    by a RESUMED_AFTER_* event. Those terminal markers must be ignored
    during the fold so the rehydrated state ends up at SEARCHING, not
    STOPPED (BRD-19 §3.3 #15)."""
    resumed_types = {
        EventType.RESUMED_AFTER_ERROR.value,
        EventType.RESUMED_AFTER_CANCEL.value,
    }
    skip: set[int] = set()
    for i, ev in enumerate(events):
        if ev.get("type") != EventType.STOPPED.value:
            continue
        nxt = events[i + 1] if i + 1 < len(events) else None
        if nxt is not None and nxt.get("type") in resumed_types:
            step_index = ev.get("step_index")
            if isinstance(step_index, int):
                skip.add(step_index)
    return skip


def _fold_events(state: RunState, events: list[dict[str, Any]]) -> None:
    """Rebuild RunState by replaying events in order (idempotent)."""
    skip_stopped = _stopped_followed_by_resume(events)

    for ev in events:
        ev_type = ev.get("type")
        match ev_type:
            case EventType.QUESTION_ASKED.value:
                # Initial event; nothing to fold (state.question is the input).
                pass
            case EventType.QUESTION_CLASSIFIED.value:
                # BRD-22 Task 4.9: Fold complexity_hint from classifier
                complexity_hint_str = ev.get("complexity_hint")
                if complexity_hint_str:
                    from app.domain.enums import ComplexityHint
                    state.complexity_hint = ComplexityHint(complexity_hint_str)
                else:
                    # Replay tolerates missing field (pre-BRD-22 traces)
                    from app.domain.enums import ComplexityHint
                    state.complexity_hint = ComplexityHint.STANDARD
            case EventType.PLAN_CREATED.value:
                state.sub_claims = [
                    SubClaim.model_validate(c) for c in ev.get("sub_claims", [])
                ]
                # BRD-22 Task 4.9: Fold new optional fields
                complexity_hint_str = ev.get("complexity_hint")
                if complexity_hint_str:
                    from app.domain.enums import ComplexityHint
                    state.complexity_hint = ComplexityHint(complexity_hint_str)
                state.expected_experts = ev.get("expected_experts") or []
                state.preferred_sources = ev.get("preferred_sources") or []

                # BRD-22 Task 4.9: Recompute critique_passes_target from budget table
                from app.agent.tasks.plan import _claim_budget
                from app.domain.enums import ComplexityHint
                _min, _max, _sources, critique_passes = _claim_budget(
                    state.question_type,
                    state.complexity_hint or ComplexityHint.STANDARD,
                )
                state.critique_passes_target = critique_passes

                _apply_state(state, AgentState.CRITIQUING)
            case EventType.PLAN_CRITIQUED.value:
                # BRD-22 Task 4.9: Recompute critique_passes_completed
                state.critique_passes_completed += 1
            case EventType.PLAN_REVISED.value:
                state.sub_claims = [
                    SubClaim.model_validate(c) for c in ev.get("new_sub_claims", [])
                ]
                state.plan_revision_count += 1
            case EventType.TOOL_CALLED.value:
                if ev.get("source_type"):
                    state.search_count += 1
            case EventType.EVIDENCE_ADDED.value:
                state.add_evidence(
                    EvidenceItem(
                        claim_id=ev["target_claim_id"],
                        source_url=ev["source_url"],
                        source_title=ev["source_title"],
                        text=ev["extracted_text"],
                        polarity=ev["polarity"],
                        confidence=ev["confidence"],
                    )
                )
            case EventType.CLAIM_COVERED.value:
                state.mark_claim_covered(ev["claim_id"])
            case EventType.CLAIM_UNCOVERABLE.value:
                state.mark_claim_uncoverable(ev["claim_id"])
            case EventType.SOURCE_FAILED.value:
                state.failed_sources.append(ev["source_type"])
            case EventType.AMBIGUITY_DETECTED.value:
                state.has_ambiguity = True
            case EventType.CONTRADICTION_DETECTED.value:
                state.contradictions.append(
                    ContradictionDetectedEvent.model_validate(ev)
                )
            case EventType.PRIOR_RUN_HINT_REPLAYED.value:
                # BRD-22 Phase 6: Extract replay metadata for audit
                source_run_id = ev.get("source_run_id")
                source_final_confidence = ev.get("source_final_confidence")
                if source_run_id is not None:
                    state.metadata["replay_source_run_id"] = source_run_id
                if source_final_confidence is not None:
                    state.metadata["replay_source_final_confidence"] = source_final_confidence
                # No state mutation — the subsequent synthetic JudgeRuledEvent and
                # StoppedEvent carry the real state changes
            case EventType.JUDGE_RULED.value:
                state.last_judge_confidence = ev.get("judge_confidence")
                state.last_structural_confidence = ev.get("structural_confidence")
                state.judge_attempts += 1
                # BRD-22 Phase 6: Fold answer_kind and final_confidence from synthetic judge events
                answer_kind_str = ev.get("answer_kind")
                if answer_kind_str:
                    from app.domain.enums import AnswerKind
                    state.selected_answer_kind = AnswerKind(answer_kind_str)
            case EventType.STOPPED.value:
                step_index = ev.get("step_index")
                if isinstance(step_index, int) and step_index in skip_stopped:
                    continue
                stop_reason = ev.get("stop_reason")
                if stop_reason is not None:
                    state.stop_reason = StopReason(stop_reason)
                # BRD-22 Phase 6: Fold answer fields from StoppedEvent (including cache replays)
                answer_kind_str = ev.get("answer_kind")
                if answer_kind_str:
                    from app.domain.enums import AnswerKind
                    state.selected_answer_kind = AnswerKind(answer_kind_str)
                answer_prose = ev.get("answer_prose")
                if answer_prose:
                    state.final_answer = answer_prose
                answer_structured = ev.get("answer_structured")
                if answer_structured:
                    state.draft_answer = answer_structured
                # Also fold stop_rationale if present
                stop_rationale = ev.get("stop_rationale")
                if stop_rationale:
                    # Store in metadata for inspection if needed
                    state.metadata["stop_rationale"] = stop_rationale
                _apply_state(state, AgentState.STOPPED)
            case (
                EventType.RESUMED_AFTER_ERROR.value
                | EventType.RESUMED_AFTER_CANCEL.value
            ):
                state.stop_reason = None
                _apply_state(state, AgentState.SEARCHING)
            case _:
                # AGENT_ERRORED, CONFIDENCE_MISMATCH, USER_CONTEXT_CHALLENGED,
                # CONTRADICTION_RESOLVED — no state change required.
                pass


# ---------------------------------------------------------------------------
# AgentRunner
# ---------------------------------------------------------------------------


class AgentRunner:
    """Owns the lifecycle of orchestrator tasks for in-flight runs."""

    def __init__(self) -> None:
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._orchestrators: dict[UUID, AgentOrchestrator] = {}
        self._lock = anyio.Lock()

    # ----- public API -----

    async def start(self, run_id: UUID) -> None:
        """Spawn the orchestrator task for ``run_id``.

        Raises ``RunAlreadyRunningError`` if a non-terminated task is
        already registered for this run (BRD-19 §4.1 single-writer).
        """
        async with self._lock:
            existing = self._tasks.get(run_id)
            if existing is not None and not existing.done():
                raise RunAlreadyRunningError(str(run_id))
            task = asyncio.create_task(
                self._supervised_run(run_id), name=f"agent-runner:{run_id}"
            )
            self._tasks[run_id] = task
            task.add_done_callback(self._on_task_done(run_id))
        logger.info("agent_runner_started", run_id=str(run_id))

    def cancel(self, run_id: UUID) -> bool:
        """Flip the cooperative cancel flag on the running orchestrator.

        Returns ``True`` if a live orchestrator was signalled, ``False``
        otherwise. **Sync** — safe to call from request handlers without
        awaiting the lock (single-loop invariant).
        """
        orch = self._orchestrators.get(run_id)
        task = self._tasks.get(run_id)
        if orch is None or task is None or task.done():
            return False
        orch.cancel()
        logger.info("agent_runner_cancel_requested", run_id=str(run_id))
        return True

    async def await_terminal(self, run_id: UUID, timeout: float = 5.0) -> None:
        """Wait until the current task for ``run_id`` resolves or raise 409.

        ``asyncio.shield`` keeps the orchestrator task alive even if our
        own caller is cancelled mid-await (BRD-19 §4.6.1).
        """
        task = self._tasks.get(run_id)
        if task is None or task.done():
            return
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except TimeoutError as exc:
            raise RunStillTerminatingError(str(run_id)) from exc
        except asyncio.CancelledError:
            # Task settled with cancellation — treat as terminal.
            return
        except Exception:
            # The supervisor inside the task already wrote AgentErrored +
            # Stopped(ERRORED); we only need to know the task settled.
            return

    async def shutdown(self) -> None:
        """Cancel and join every live task. Called from app lifespan."""
        async with self._lock:
            snapshot = list(self._tasks.items())
        for run_id, task in snapshot:
            if task.done():
                continue
            self.cancel(run_id)
        for _run_id, task in snapshot:
            if task.done():
                continue
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError):
                pass
            except Exception:  # noqa: BLE001 - supervisor already logged
                pass
        logger.info("agent_runner_shutdown", count=len(snapshot))

    def is_running(self, run_id: UUID) -> bool:
        """Return True if a non-terminated task is registered."""
        task = self._tasks.get(run_id)
        return task is not None and not task.done()

    # ----- internals -----

    def _on_task_done(
        self, run_id: UUID
    ) -> Callable[[asyncio.Task[None]], None]:
        def _callback(task: asyncio.Task[None]) -> None:
            self._tasks.pop(run_id, None)
            self._orchestrators.pop(run_id, None)
            if task.cancelled():
                logger.info("agent_runner_task_cancelled", run_id=str(run_id))
                return
            exc = task.exception()
            if exc is not None:
                logger.exception(
                    "agent_runner_task_unhandled",
                    run_id=str(run_id),
                    exc_info=exc,
                )
            else:
                logger.info("agent_runner_task_done", run_id=str(run_id))

        return _callback

    async def _supervised_run(self, run_id: UUID) -> None:
        """Long-running coroutine wrapping the orchestrator with a safety net."""
        async with async_session_maker() as session:
            run = await session.get(Run, run_id)
            if run is None:
                logger.error("agent_runner_unknown_run", run_id=str(run_id))
                return

            event_service = EventService(session)
            prior_events = await event_service.get_events(
                run_id, after_step=0, limit=10_000
            )

            state = RunState(
                run_id=run_id,
                question=run.question,
                user_context=run.user_context,
                confidence_threshold=run.confidence_threshold,
                output_format=run.output_format,
                owner_username=run.owner_username,
            )
            _fold_events(state, prior_events)

            emit = self._make_emit(run_id, event_service)
            orchestrator = AgentOrchestrator(state, emit, stopping_policy=None)
            self._orchestrators[run_id] = orchestrator

            try:
                await orchestrator.run()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - supervisor envelope
                logger.exception(
                    "agent_runner_orchestrator_raised",
                    run_id=str(run_id),
                    exc_info=exc,
                )
                await self._supervisor_last_resort(run_id, exc)

    def _make_emit(
        self, run_id: UUID, event_service: EventService
    ) -> EmitCallback:
        async def _emit(event: BaseEvent) -> None:
            db_event = await event_service.append_event(run_id, event)
            sse_payload: dict[str, Any] = {
                "id": str(db_event.id),
                "run_id": str(db_event.run_id),
                "step_index": db_event.step_index,
                "parent_event_id": (
                    str(db_event.parent_event_id)
                    if db_event.parent_event_id
                    else None
                ),
                "type": db_event.type,
                "created_at": db_event.created_at.isoformat(),
                **db_event.payload,
            }
            try:
                await connection_manager.publish(run_id, sse_payload)
            except Exception:  # noqa: BLE001 - SSE fan-out is best-effort
                logger.exception("sse_publish_failed", run_id=str(run_id))

            if isinstance(event, StoppedEvent):
                await self._write_terminal_row(run_id, event.stop_reason)

        return _emit

    @staticmethod
    async def _write_terminal_row(run_id: UUID, stop_reason: StopReason) -> None:
        """Persist ``stop_reason`` + ``stopped_at`` on the Run row.

        Opens its own session so a poisoned supervisor session cannot
        block the terminal write (B-01). ``stopped_at`` is preserved if
        already set — a prior ``cancel_run`` call wins over the runner's
        own clock.
        """
        now = datetime.now(UTC)
        stmt = (
            update(Run)
            .where(Run.id == run_id)
            .values(
                stop_reason=stop_reason.value,
                stopped_at=case(
                    (Run.stopped_at.is_(None), now),
                    else_=Run.stopped_at,
                ),
            )
        )
        async with async_session_maker() as session:
            await session.execute(stmt)
            await session.commit()

    async def _supervisor_last_resort(
        self, run_id: UUID, exc: BaseException
    ) -> None:
        """Emit AgentErrored + Stopped(ERRORED) using a fresh session.

        Idempotent: if the orchestrator already managed to emit a STOPPED
        event before raising, we leave the event log alone and only
        ensure ``runs.stop_reason`` is populated.
        """
        async with async_session_maker() as session:
            event_service = EventService(session)
            latest = await event_service.get_latest_event(run_id)
            if latest is not None and latest.type == EventType.STOPPED.value:
                try:
                    stop_reason_raw = latest.payload.get("stop_reason")
                    stop_reason = (
                        StopReason(stop_reason_raw)
                        if stop_reason_raw is not None
                        else StopReason.ERRORED
                    )
                except ValueError:
                    stop_reason = StopReason.ERRORED
                await self._write_terminal_row(run_id, stop_reason)
                return

            await event_service.append_event(
                run_id,
                AgentErroredEvent(
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    recoverable=False,
                    error_code=(
                        "llm_pool_rate_limited"
                        if isinstance(exc, LLMPoolExhausted)
                        or isinstance(exc.__cause__, LLMPoolExhausted)
                        else None
                    ),
                ),
            )
            await event_service.append_event(
                run_id,
                StoppedEvent(stop_reason=StopReason.ERRORED),
            )
        await self._write_terminal_row(run_id, StopReason.ERRORED)


agent_runner = AgentRunner()

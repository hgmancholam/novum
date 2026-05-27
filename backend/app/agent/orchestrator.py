"""Agent FSM orchestrator (BRD-07).

Pure in-memory engine. Emits ``BaseEvent`` instances through an injected
async callback; does NOT persist, stream, or implement the layered
stopping policy (those belong to BRD-09 / BRD-10).
"""

from __future__ import annotations

import traceback
from collections.abc import Awaitable, Callable

import structlog

from app.agent.run_state import RunState
from app.agent.states import AgentState
from app.agent.tasks import (
    analyze_evidence,
    classify_question,
    create_plan,
    critique_plan,
    draft_answer,
    evaluate_with_judge,
    execute_search_round,
    map_issues_to_claims,
    normalize_question,
    revise_plan,
)
from app.confidence import detect_mismatch
from app.domain.enums import StopReason
from app.domain.events import (
    AgentErroredEvent,
    BaseEvent,
    ConfidenceMismatchEvent,
    QuestionAskedEvent,
    StoppedEvent,
)
from app.llm.client import count_tokens
from app.stopping import StoppingPolicy

logger = structlog.get_logger(__name__)


type EventCallback = Callable[[BaseEvent], Awaitable[None]]


class AgentOrchestrator:
    """Drives a ``RunState`` through the research FSM."""

    def __init__(
        self,
        state: RunState,
        emit: EventCallback,
        stopping_policy: StoppingPolicy | None = None,
    ) -> None:
        self.state = state
        self._emit = emit
        self._cancelled = False
        self._stopping_policy = stopping_policy or StoppingPolicy()

    def cancel(self) -> None:
        """Request graceful cancellation before the next handler iteration."""
        self._cancelled = True

    async def emit(self, event: BaseEvent) -> None:
        await self._emit(event)

    async def run(self) -> StopReason:
        """Execute the FSM until a terminal state."""
        await self.emit(
            QuestionAskedEvent(
                question=self.state.question,
                user_context=self.state.user_context,
                detected_question_type=None,
            )
        )
        self.state.total_tokens += count_tokens(self.state.question)

        await self._normalize_question()

        if not await self._detect_question_type():
            return StopReason.HONEST_UNANSWERABLE

        try:
            self.state.transition_to(AgentState.PLANNING)
            while self.state.current_state not in (
                AgentState.STOPPED,
                AgentState.ERRORED,
            ):
                if self._cancelled:
                    return await self._stop(StopReason.USER_CANCELLED)

                self.state.iteration_count += 1
                match self.state.current_state:
                    case AgentState.PLANNING:
                        await self._handle_planning()
                    case AgentState.CRITIQUING:
                        await self._handle_critiquing()
                    case AgentState.REVISING:
                        await self._handle_revising()
                    case AgentState.SEARCHING:
                        await self._handle_searching()
                    case AgentState.ANALYZING:
                        await self._handle_analyzing()
                    case AgentState.DRAFTING:
                        await self._handle_drafting()
                    case AgentState.JUDGING:
                        await self._handle_judging()
                    case _:
                        break
        except Exception as exc:  # noqa: BLE001 - top-level error envelope
            return await self._handle_error(exc)

        return self.state.stop_reason or StopReason.ERRORED

    async def _detect_question_type(self) -> bool:
        mapped, _ = await classify_question(self.state.question)
        if mapped is None:
            await self._stop(StopReason.HONEST_UNANSWERABLE)
            return False
        self.state.question_type = mapped
        return True

    async def _normalize_question(self) -> None:
        """Clean typos / informal phrasing before classification.

        Replaces ``state.question`` with the normalized form so downstream
        LLM steps see the cleaner input. The original is preserved in the
        emitted ``QuestionNormalizedEvent``. Failures are swallowed: a
        broken normalizer must not block the rest of the pipeline.
        """
        try:
            event = await normalize_question(self.state.question)
        except Exception as exc:  # noqa: BLE001 - non-critical step
            logger.warning(
                "normalize_question_failed",
                error=str(exc),
                run_id=str(self.state.run_id),
            )
            return
        await self.emit(event)
        if event.normalized_question and event.normalized_question != self.state.question:
            self.state.question = event.normalized_question

    async def _handle_planning(self) -> None:
        event = await create_plan(self.state.question)
        self.state.sub_claims = list(event.sub_claims)
        await self.emit(event)
        self.state.transition_to(AgentState.CRITIQUING)

    async def _handle_critiquing(self) -> None:
        critique = await critique_plan(self.state.question, self.state.sub_claims)
        await self.emit(critique)
        if critique.acceptable:
            self.state.transition_to(AgentState.SEARCHING)
            return
        if self.state.plan_revision_count >= self.state.max_plan_revisions:
            self.state.transition_to(AgentState.SEARCHING)
            return
        self.state.transition_to(AgentState.REVISING)

    async def _handle_revising(self) -> None:
        self.state.plan_revision_count += 1
        revised = await revise_plan(
            self.state.question,
            self.state.sub_claims,
            attempt_number=self.state.plan_revision_count,
            critique_issues=None,
        )
        await self.emit(revised)
        self.state.sub_claims = list(revised.new_sub_claims)
        self.state.transition_to(AgentState.CRITIQUING)

    async def _handle_searching(self) -> None:
        result = await self._stopping_policy.evaluate(self.state)
        if self._stopping_policy.should_stop(result):
            if result.stop_reason is None:
                raise RuntimeError("Stopping signal returned STOP without a stop_reason")
            await self._stop(result.stop_reason)
            return
        events = await execute_search_round(self.state)
        for ev in events:
            await self.emit(ev)
        self.state.search_count += 1
        self.state.transition_to(AgentState.ANALYZING)

    async def _handle_analyzing(self) -> None:
        events = await analyze_evidence(self.state)
        for ev in events:
            await self.emit(ev)

        if self.state.all_claims_resolved():
            if self.state.covered_claims:
                self.state.transition_to(AgentState.DRAFTING)
                return
            # No coverage and no pending claims — let the policy decide between
            # BUDGET (search_count >= max_searches) and HONEST_UNANSWERABLE.
            result = await self._stopping_policy.evaluate(self.state)
            if self._stopping_policy.should_stop(result):
                if result.stop_reason is None:
                    raise RuntimeError(
                        "Stopping signal returned STOP without a stop_reason"
                    )
                await self._stop(result.stop_reason)
            else:
                # Defensive: total_claims==0 case is impossible after planning.
                await self._stop(StopReason.HONEST_UNANSWERABLE)
            return

        result = await self._stopping_policy.evaluate(self.state)
        if self._stopping_policy.should_stop(result):
            if result.stop_reason is None:
                raise RuntimeError("Stopping signal returned STOP without a stop_reason")
            # Budget stops still let a partial draft proceed when we have
            # covered claims — honest stops always terminate immediately.
            if (
                result.stop_reason is StopReason.STOPPED_BY_BUDGET
                and self.state.covered_claims
            ):
                self.state.transition_to(AgentState.DRAFTING)
            else:
                await self._stop(result.stop_reason)
            return

        self.state.transition_to(AgentState.SEARCHING)

    async def _handle_drafting(self) -> None:
        await draft_answer(self.state)
        self.state.transition_to(AgentState.JUDGING)

    async def _handle_judging(self) -> None:
        judge_event = await evaluate_with_judge(self.state)
        await self.emit(judge_event)
        self.state.last_judge_confidence = judge_event.judge_confidence
        self.state.last_structural_confidence = judge_event.structural_confidence
        self.state.judge_attempts += 1

        result = await self._stopping_policy.evaluate(
            self.state,
            judge_confidence=judge_event.judge_confidence,
        )
        if self._stopping_policy.should_stop(result):
            if result.stop_reason is None:
                raise RuntimeError("Stopping signal returned STOP without a stop_reason")
            await self._stop(result.stop_reason)
            return

        # Judge sub-loop safety net (O-07): not part of the layered policy.
        if self.state.judge_attempts >= self.state.max_judge_attempts:
            # O-09: never silently confirm.
            await self._stop(StopReason.STOPPED_BY_BUDGET)
            return

        # RF-15 disconfirmation (BRD-08, untouched by BRD-09).
        mismatch = detect_mismatch(
            structural=judge_event.structural_confidence,
            judge=judge_event.judge_confidence,
        )
        if mismatch.has_mismatch:
            if mismatch.trust_flag is None:
                raise RuntimeError("Mismatch detected without a trust_flag")
            await self.emit(
                ConfidenceMismatchEvent(
                    structural_confidence=judge_event.structural_confidence,
                    judge_confidence=judge_event.judge_confidence,
                    divergence=mismatch.divergence,
                    trust_flag=mismatch.trust_flag,
                )
            )

        issues = judge_event.suggested_improvements or []
        if issues:
            claim_ids = await map_issues_to_claims(issues[:2], self.state.sub_claims)
            for cid in claim_ids:
                for c in self.state.sub_claims:
                    if c.id == cid and c.status == "covered":
                        c.status = "pending"
                        if cid in self.state.covered_claims:
                            self.state.covered_claims.remove(cid)

        self.state.transition_to(AgentState.SEARCHING)

    async def _handle_error(self, exc: BaseException) -> StopReason:
        logger.error(
            "agent_run_error",
            run_id=str(self.state.run_id),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        await self.emit(
            AgentErroredEvent(
                error_type=type(exc).__name__,
                error_message=str(exc),
                stack_trace=traceback.format_exc(),
                recoverable=False,
                recovery_suggestion=None,
            )
        )
        return await self._stop(StopReason.ERRORED)

    async def _stop(self, reason: StopReason) -> StopReason:
        self.state.stop_reason = reason
        if self.state.current_state not in (AgentState.STOPPED, AgentState.ERRORED):
            target = AgentState.ERRORED if reason == StopReason.ERRORED else AgentState.STOPPED
            self.state.transition_to(target)
        answer = self.state.draft_answer if reason == StopReason.JUDGE_CONFIRMED else None
        if reason == StopReason.JUDGE_CONFIRMED:
            self.state.final_answer = answer
        await self.emit(
            StoppedEvent(
                stop_reason=reason,
                answer_prose=answer,
                total_tokens=self.state.total_tokens,
            )
        )
        logger.info(
            "agent_run_complete",
            run_id=str(self.state.run_id),
            stop_reason=reason.value,
            iterations=self.state.iteration_count,
        )
        return reason

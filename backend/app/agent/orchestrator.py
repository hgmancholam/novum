"""Agent FSM orchestrator (BRD-07, WP-3 early-stop + StopRationale).

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
from app.confidence import (
    calculate_agreement,
    calculate_coverage,
    detect_mismatch,
)
from app.domain.enums import StopReason
from app.domain.events import (
    AgentErroredEvent,
    BaseEvent,
    ConfidenceMismatchEvent,
    QuestionAskedEvent,
    StoppedEvent,
    StopRationale,
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
        # Prelude runs only on a fresh start (INIT). For resumed runs,
        # ``_fold_events`` has already placed the state somewhere in the
        # FSM (typically SEARCHING), so we skip straight into the loop.
        is_fresh = self.state.current_state == AgentState.INIT
        if is_fresh:
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
            if is_fresh:
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
        """Classify question type (WP-1 always returns a type, no short-circuit)."""
        mapped, _ = await classify_question(self.state.question)
        if mapped is None:
            # Defensive: classifier should never return None post-WP-1.
            # If it does, default to FACTUAL and let resolver pick the right kind.
            from app.domain.enums import QuestionType
            mapped = QuestionType.FACTUAL
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
        event = await create_plan(
            self.state.question,
            question_type=self.state.question_type,
        )
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
            question_type=self.state.question_type,
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

        # WP-4: Check saturation after each evidence round
        from app.config import settings as cfg
        from app.domain.events import SaturationDetectedEvent
        from app.stopping.signals.saturation import evaluate_saturation

        saturation_result = await evaluate_saturation(self.state)
        # Update last_novelty regardless of whether signal fires
        # (judge prompt will include it as evidence_saturation)

        if saturation_result.result.value == "defer" and saturation_result.explanation and "saturated" in saturation_result.explanation.lower():
            # Signal detected saturation — emit event
            await self.emit(
                SaturationDetectedEvent(
                    round_index=self.state.search_count,
                    novelty=self.state.last_novelty or 0.0,
                    k=cfg.saturation_window,
                    threshold=cfg.novelty_floor,
                )
            )

        if self.state.all_claims_resolved():
            # WP-3: always proceed to draft, even with zero covered claims.
            # The resolver will select BEST_EFFORT or ETHICAL_REDIRECT as needed.
            self.state.transition_to(AgentState.DRAFTING)
            return

        result = await self._stopping_policy.evaluate(self.state)
        if self._stopping_policy.should_stop(result):
            if result.stop_reason is None:
                raise RuntimeError("Stopping signal returned STOP without a stop_reason")
            # WP-3: budget stops with any coverage proceed to draft (resolver decides kind).
            if result.stop_reason is StopReason.STOPPED_BY_BUDGET:
                self.state.transition_to(AgentState.DRAFTING)
            else:
                await self._stop(result.stop_reason)
            return

        self.state.transition_to(AgentState.SEARCHING)

    async def _handle_drafting(self) -> None:
        await draft_answer(self.state)
        self.state.transition_to(AgentState.JUDGING)

    async def _handle_judging(self) -> None:
        # WP-5: Pass emit callback for JudgeProviderDegradedEvent
        judge_event = await evaluate_with_judge(self.state, emit_event=self.emit)
        await self.emit(judge_event)
        self.state.last_judge_confidence = judge_event.judge_confidence
        self.state.last_structural_confidence = judge_event.structural_confidence
        self.state.last_coverage = calculate_coverage(self.state)
        self.state.last_agreement = calculate_agreement(self.state.evidence)
        self.state.judge_attempts += 1

        # WP-3 G8: Early-stop for trivial-fact questions (matrix row 1).
        # When coverage=1.0 AND C_agreement≥0.9 AND J≥0.85 on any round, stop immediately.
        from app.config import settings
        if (
            judge_event.passed
            and self.state.last_coverage >= 1.0
            and self.state.last_agreement >= settings.early_stop_min_agreement
            and judge_event.judge_confidence >= settings.early_stop_min_judge
        ):
            await self._stop(StopReason.JUDGE_CONFIRMED)
            return

        result = await self._stopping_policy.evaluate(
            self.state,
            judge_confidence=judge_event.judge_confidence,
            judge_passed=judge_event.passed,
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
        """Transition to terminal state and emit StoppedEvent with StopRationale (WP-3 G2)."""
        self.state.stop_reason = reason
        if self.state.current_state not in (AgentState.STOPPED, AgentState.ERRORED):
            target = AgentState.ERRORED if reason == StopReason.ERRORED else AgentState.STOPPED
            self.state.transition_to(target)
        answer = self.state.draft_answer if reason == StopReason.JUDGE_CONFIRMED else None
        answer_structured: str | None = None
        answer_kind = self.state.selected_answer_kind if reason == StopReason.JUDGE_CONFIRMED else None

        # BRD-16: render BOTH formats at stop time for client-side switching
        if reason == StopReason.JUDGE_CONFIRMED and answer:
            from app.output import renderer_registry
            from app.seams.output import RenderContext

            seen: set[str] = set()
            sources: list[dict] = []
            for ev in self.state.evidence:
                if ev.source_url not in seen:
                    seen.add(ev.source_url)
                    sources.append({"url": ev.source_url, "title": ev.source_title, "domain": ""})

            render_ctx = RenderContext(
                question=self.state.question,
                answer_content=answer,
                sources=sources,
                confidence=self.state.last_judge_confidence or 0.0,
                stop_reason=reason.value,
            )
            # Always render prose as the canonical answer_prose
            prose_renderer = renderer_registry.get("prose") or renderer_registry.get_default()
            answer = prose_renderer.render(render_ctx).content

            # Always render structured for instant client-side format switching
            struct_renderer = renderer_registry.get("structured") or renderer_registry.get_default()
            answer_structured = struct_renderer.render(render_ctx).content

        if reason == StopReason.JUDGE_CONFIRMED:
            self.state.final_answer = answer

        # WP-3 G2: Build StopRationale for every terminal (optional for non-judge terminals).
        stop_rationale: StopRationale | None = None
        if reason == StopReason.JUDGE_CONFIRMED:
            triggering_signal = (
                "early_stop"
                if (
                    self.state.last_coverage >= 1.0
                    and self.state.last_agreement >= 0.9
                    and (self.state.last_judge_confidence or 0.0) >= 0.85
                )
                else "judge"
            )
            summary = f"Answered as {answer_kind.value if answer_kind else 'unknown'} with confidence {self.state.last_judge_confidence or 0.0:.2f}"
            stop_rationale = StopRationale(
                reason=reason,
                triggering_signal=triggering_signal,
                summary=summary,
                confidence=self.state.last_judge_confidence,
            )
        elif reason == StopReason.STOPPED_BY_BUDGET:
            stop_rationale = StopRationale(
                reason=reason,
                triggering_signal="budget",
                summary=f"Reached search limit ({self.state.search_count} rounds)",
                confidence=self.state.last_judge_confidence,
            )
        elif reason == StopReason.USER_CANCELLED:
            stop_rationale = StopRationale(
                reason=reason,
                triggering_signal="user",
                summary="User cancelled the run",
                confidence=None,
            )
        elif reason == StopReason.ERRORED:
            stop_rationale = StopRationale(
                reason=reason,
                triggering_signal="error",
                summary="Run terminated due to an error",
                confidence=None,
            )

        await self.emit(
            StoppedEvent(
                stop_reason=reason,
                answer_prose=answer,
                answer_structured=answer_structured,
                answer_kind=answer_kind,
                stop_rationale=stop_rationale,
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

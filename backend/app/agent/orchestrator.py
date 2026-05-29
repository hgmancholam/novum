"""Agent FSM orchestrator (BRD-07, WP-3 early-stop + StopRationale).

Pure in-memory engine. Emits ``BaseEvent`` instances through an injected
async callback; does NOT persist, stream, or implement the layered
stopping policy (those belong to BRD-09 / BRD-10).
"""

from __future__ import annotations

import traceback
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Literal

import structlog

from app.agent.run_state import RunState
from app.agent.states import AgentState
from app.agent.tasks import (
    analyze_evidence,
    classify_question,
    create_plan,
    critique_plan,
    detect_empty_comparative,
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
from app.domain.enums import ComplexityHint, Lane, QuestionType, StopReason
from app.domain.events import (
    AdversarialObjectionsGeneratedEvent,
    AgentErroredEvent,
    BaseEvent,
    ConfidenceMismatchEvent,
    MetaStopVerdictEvent,
    QuestionAskedEvent,
    QuestionClassifiedEvent,
    RouteSelectedEvent,
    StoppedEvent,
    StopRationale,
)
from app.llm.client import LLMPoolExhausted, LLMProviderQuotaExhausted, count_tokens, llm
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
        # PR-1 (post-2026-05-29 eval): mirror every emitted event into the
        # in-memory ``state.events`` list so ``has_event()`` works for fresh
        # runs (not just resume) and ``_check_global_budget`` can derive event
        # counters and the no-progress plateau predicate without a DB roundtrip.
        self.state.events.append(event)
        await self._emit(event)

    async def run(self) -> StopReason:
        """Execute the FSM until a terminal state."""
        # Prelude runs only on a fresh start (INIT). For resumed runs,
        # ``_fold_events`` has already placed the state somewhere in the
        # FSM (typically SEARCHING), so we skip straight into the loop.
        is_fresh = self.state.current_state == AgentState.INIT
        if is_fresh:
            # BRD-22 Phase 6: Try instant cache replay BEFORE emitting QuestionAskedEvent
            from app.agent.instant_cache import try_replay

            cached = try_replay(self.state.owner_username, self.state.question)
            if cached is not None:
                # Cache hit — emit canonical opener, then replay events and stop
                await self.emit(
                    QuestionAskedEvent(
                        question=self.state.question,
                        user_context=self.state.user_context,
                        detected_question_type=None,
                    )
                )
                self.state.total_tokens += count_tokens(self.state.question)
                # Cancel observed between QuestionAsked emit and replay wins over replay
                if self._cancelled:
                    await self._stop(StopReason.USER_CANCELLED)
                    return StopReason.USER_CANCELLED
                return await self._stop_from_cache(cached)

            # Cache miss — proceed with normal flow
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

            # IP-25 Phase A: Select lane and emit RouteSelectedEvent (T-25-A-05)
            # Telemetry only — all lanes continue through STANDARD flow for now
            from app.agent.lane_router import apply_lane_budgets, select_lane

            lane, reason = select_lane(
                question_type=self.state.question_type or QuestionType.FACTUAL,
                complexity_hint=self.state.complexity_hint or ComplexityHint.STANDARD,
                temporal_sensitivity=self.state.temporal_sensitivity,
                ambiguity_detected=self.state.has_ambiguity,
            )
            self.state.selected_lane = lane
            # PR-1: hard global caps (wall-clock + counters) for this lane.
            apply_lane_budgets(self.state, lane)
            await self.emit(
                RouteSelectedEvent(
                    lane=lane,
                    reason=reason,
                    question_type=self.state.question_type or QuestionType.FACTUAL,
                    complexity_hint=self.state.complexity_hint or ComplexityHint.STANDARD,
                    temporal_sensitivity=self.state.temporal_sensitivity,
                )
            )

            # IP-25 Phase C: FAST lane execution (T-25-C-03)
            if lane == Lane.FAST:
                from app.agent.lanes.fast import execute_fast_lane
                from app.domain.events import LaneEscalatedEvent

                result = await execute_fast_lane(self.state, self.emit)
                if result == "escalate":
                    # Escalate to STANDARD lane
                    await self.emit(
                        LaneEscalatedEvent(
                            from_lane=Lane.FAST,
                            to_lane=Lane.STANDARD,
                            reason="mini_judge_rejected_or_low_S",
                        )
                    )
                    # Fall through to normal STANDARD pipeline
                else:
                    # FAST lane succeeded — finalize and exit
                    await self._stop(result)
                    return result

            # IP-25 Phase E: DEEP lane execution (T-25-E-08)
            if lane == Lane.DEEP:
                from app.agent.lanes.deep import execute_deep_lane

                result = await execute_deep_lane(self.state, self.emit)
                # DEEP lane always returns a definitive StopReason
                await self._stop(result)
                return result

        try:
            if is_fresh:
                # PR-4 Mejora 4.2: short-circuit STANDARD planning when the
                # question is ambiguous. With no plan/evidence the synth still
                # produces a BEST_EFFORT clarification (draft.py reads the
                # AmbiguityDetected event directly) and the run finishes in
                # seconds instead of executing PLANNING→SEARCHING→ANALYZING
                # for a question that cannot be researched.
                if self.state.has_ambiguity:
                    self.state.transition_to(AgentState.DRAFTING)
                else:
                    self.state.transition_to(AgentState.PLANNING)
            while self.state.current_state not in (
                AgentState.STOPPED,
                AgentState.ERRORED,
            ):
                if self._cancelled:
                    return await self._stop(StopReason.USER_CANCELLED)

                # PR-1 (post-2026-05-29 eval): FSM-independent stop guard.
                # Runs the wall-clock + global-counter + event-plateau checks
                # BEFORE phase dispatch so a stuck SEARCHING↔ANALYZING cycle
                # cannot escape with no terminal Stopped event.
                if await self._check_global_budget():
                    return self.state.stop_reason or StopReason.STOPPED_BY_BUDGET

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
        """Classify question type + derive complexity hint (BRD-22).

        Returns:
            True (always continues; WP-1 removed the short-circuit path).

        Emits:
            QuestionClassifiedEvent with question_type, classifier_confidence,
            complexity_hint, and heuristic_signals.

        WP-2 G9: also runs the empty-comparative detector and emits
        ``AmbiguityDetectedEvent`` for underspecified comparatives so that
        ``draft.py`` derives ``ambiguity_flag=True`` and the resolver routes
        the run to ``BEST_EFFORT`` per §0.8 row 3.

        BRD-22 (Task 3.4): captures complexity_hint from classifier and emits it
        in QuestionClassifiedEvent. The complexity_hint and expected_experts will
        be stored in RunState later in Task 4.6/4.7 when the planner uses them.
        """
        # BRD-22: classify_question now returns 4-tuple
        mapped, verdict, complexity_hint, heuristic_signals = await classify_question(
            self.state.question
        )
        if mapped is None:
            # Defensive: classifier should never return None post-WP-1.
            # If it does, default to FACTUAL and let resolver pick the right kind.
            from app.domain.enums import QuestionType
            mapped = QuestionType.FACTUAL

        self.state.question_type = mapped
        # BRD-22 Task 3.4: Store complexity_hint in RunState for planner
        self.state.complexity_hint = complexity_hint

        # BRD-23 WP-1: derive temporal sensitivity deterministically (no LLM)
        from app.agent.tasks.classify import derive_temporal_sensitivity
        temporal = derive_temporal_sensitivity(self.state.question, mapped)
        self.state.temporal_sensitivity = temporal

        # Emit QuestionClassifiedEvent with BRD-22 + BRD-23 fields
        await self.emit(
            QuestionClassifiedEvent(
                question_type=mapped,
                classifier_confidence=verdict.confidence or 1.0,
                complexity_hint=complexity_hint,
                heuristic_signals=heuristic_signals,
                temporal_sensitivity=temporal,
            )
        )

        try:
            ambiguity_event = await detect_empty_comparative(
                self.state.question, mapped
            )
        except Exception as exc:  # noqa: BLE001 - non-critical step
            logger.warning(
                "detect_empty_comparative_failed",
                error=str(exc),
                run_id=str(self.state.run_id),
            )
            ambiguity_event = None
        if ambiguity_event is not None:
            await self.emit(ambiguity_event)
            # PR-4 Mejora 4.2: keep live state in sync with the event log so
            # downstream consumers (lane router, draft.py answer-kind resolver,
            # short-circuit below) observe ambiguity without depending on a
            # later replay pass.
            self.state.has_ambiguity = True
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
        """Create initial plan (BRD-22: with complexity_hint + experts)."""
        event = await create_plan(
            self.state.question,
            question_type=self.state.question_type,
            complexity_hint=self.state.complexity_hint,
            temporal_sensitivity=self.state.temporal_sensitivity,
        )
        self.state.sub_claims = list(event.sub_claims)

        # BRD-22 Task 4.7: Store expected_experts and preferred_sources
        self.state.expected_experts = list(event.expected_experts or [])
        self.state.preferred_sources = list(event.preferred_sources or [])

        # BRD-22 Task 4.7: Compute critique_passes_target from budget table
        from app.agent.tasks.plan import _claim_budget
        from app.domain.enums import ComplexityHint

        _min, _max, _sources_per_claim, critique_passes = _claim_budget(
            self.state.question_type,
            self.state.complexity_hint or ComplexityHint.STANDARD,
        )
        self.state.critique_passes_target = critique_passes

        await self.emit(event)

        # BRD-22 Task 4.7: Skip CRITIQUING when target == 0 (trivial path)
        if self.state.critique_passes_target == 0:
            self.state.transition_to(AgentState.SEARCHING)
        else:
            self.state.transition_to(AgentState.CRITIQUING)

    async def _handle_critiquing(self) -> None:
        """Critique plan (BRD-22 Task 4.8: forced extra pass for deep)."""
        # BRD-22 Task 4.8: Increment counter at top
        self.state.critique_passes_completed += 1

        critique = await critique_plan(self.state.question, self.state.sub_claims)
        await self.emit(critique)

        # BRD-22 Task 4.8: Force REVISING when critique_passes_completed < target
        if self.state.critique_passes_completed < self.state.critique_passes_target:
            # Mandatory extra pass for deep — ignore acceptable verdict
            self.state.transition_to(AgentState.REVISING)
            return

        # Normal branching when target met
        if critique.acceptable:
            # IP-25 Phase D: Generate hypotheses for certain question types or DEEP lane
            await self._generate_hypotheses_if_needed()
            self.state.transition_to(AgentState.SEARCHING)
            return
        if self.state.plan_revision_count >= self.state.max_plan_revisions:
            # IP-25 Phase D: Generate hypotheses before transitioning
            await self._generate_hypotheses_if_needed()
            self.state.transition_to(AgentState.SEARCHING)
            return
        self.state.transition_to(AgentState.REVISING)

    async def _handle_revising(self) -> None:
        """Revise plan after critique rejection (BRD-22: pass complexity_hint)."""
        self.state.plan_revision_count += 1
        revised = await revise_plan(
            self.state.question,
            self.state.sub_claims,
            attempt_number=self.state.plan_revision_count,
            critique_issues=None,
            question_type=self.state.question_type,
            complexity_hint=self.state.complexity_hint,
        )
        await self.emit(revised)
        self.state.sub_claims = list(revised.new_sub_claims)
        self.state.transition_to(AgentState.CRITIQUING)

    async def _generate_hypotheses_if_needed(self) -> None:
        """Generate abductive hypotheses for causal/scenario questions (IP-25 Phase D).

        Triggered after planning is complete (critique accepted or max revisions hit)
        when question_type requires hypotheses or lane is DEEP.
        """
        from app.agent.tasks.hypotheses import generate_hypotheses
        from app.domain.enums import AnswerKind, Lane, QuestionType
        from app.domain.events import HypothesesGeneratedEvent

        trigger = (
            self.state.question_type in {
                QuestionType.CAUSAL,
                QuestionType.PREDICTIVE_FUTURE,
            }
            or self.state.selected_answer_kind in {AnswerKind.SCENARIO, AnswerKind.BEST_EFFORT}
            or self.state.selected_lane == Lane.DEEP
        )

        if not trigger:
            return

        try:
            hypotheses = await generate_hypotheses(self.state)
            self.state.hypotheses = hypotheses
            await self.emit(HypothesesGeneratedEvent(hypotheses=hypotheses))
        except Exception as exc:  # noqa: BLE001 - non-critical enrichment
            logger.warning(
                "hypotheses_generation_failed",
                error=str(exc),
                run_id=str(self.state.run_id),
            )

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

        # PR-5 Mejora 5.2: snapshot post-analyze coverage so the
        # claim-coverage plateau predicate can detect ``SEARCHING ↔ ANALYZING``
        # ping-pong that adds evidence without promoting any sub-claim to
        # ``covered``.
        self.state.coverage_history.append(len(self.state.covered_claims))

        # PR-2 (post-2026-05-29 eval): pre-synth meta-judge gate. Fires once
        # per run, the first time either (a) all claims are resolved (we are
        # about to enter DRAFTING) or (b) evidence_total crosses the
        # configured threshold mid-flow. May short-circuit to stop or
        # transition straight back to SEARCHING.
        if await self._maybe_run_before_synth_meta_judge():
            return

        # IP-25 Phase 0: detect echo chambers (≥3 dated sources < 7d window,
        # agreement=1.0). Emission deduped per claim across rounds.
        from app.confidence.structural import apply_echo_chamber_penalty
        _, echo_event = apply_echo_chamber_penalty(self.state, 1.0)
        if echo_event is not None and echo_event.target_claim_id not in self.state.echo_chamber_emitted_claims:
            self.state.echo_chamber_emitted_claims.add(echo_event.target_claim_id)
            await self.emit(echo_event)

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

        # IP-25 Phase B: Dynamic re-decomposition check BEFORE transitioning
        from uuid import uuid4

        from app.agent.tasks.replan import identify_plan_gaps
        from app.confidence import calculate_structural_confidence
        from app.domain.events import PlanGapsDetectedEvent, SubClaim

        structural_conf = calculate_structural_confidence(self.state)
        S_raw = structural_conf.score

        # Check re-decomposition conditions:
        # 1. Haven't hit max re-decompositions
        # 2. S_raw is below threshold + buffer
        # 3. Budget allows more search
        # PR-5 Mejora 8.2: widen the buffer to 0.20 on the FIRST re-decomp so
        # borderline runs (S just above threshold + 0.10 but still uncertain)
        # get at least one identify_plan_gaps round before drafting. Subsequent
        # rounds keep the tighter 0.10 cap.
        redecomp_buffer = 0.20 if self.state.redecomposition_count == 0 else 0.10
        if (
            self.state.redecomposition_count < self.state.max_redecomposition
            and S_raw < self.state.confidence_threshold + redecomp_buffer
            and self.state.search_count < self.state.max_searches - 1  # Need room for at least one more round
        ):
            gaps = await identify_plan_gaps(self.state)
            if gaps:
                # Add gaps as new sub-claims
                new_sub_claims = [
                    SubClaim(id=str(uuid4()), text=gap, status="pending")
                    for gap in gaps
                ]
                self.state.sub_claims.extend(new_sub_claims)
                self.state.redecomposition_count += 1

                await self.emit(
                    PlanGapsDetectedEvent(
                        gaps=gaps,
                        extra_sub_claim_ids=[c.id for c in new_sub_claims],
                    )
                )

                # Transition back to SEARCHING for new sub-claims
                self.state.transition_to(AgentState.SEARCHING)
                return

        if self.state.all_claims_resolved():
            # WP-3: always proceed to draft, even with zero covered claims.
            # The resolver will select BEST_EFFORT or ETHICAL_REDIRECT as needed.
            self.state.transition_to(AgentState.DRAFTING)
            return

        result = await self._stopping_policy.evaluate(self.state)
        if self._stopping_policy.should_stop(result):
            if result.stop_reason is None:
                raise RuntimeError("Stopping signal returned STOP without a stop_reason")
            # PR-1 Mejora 2.1: mark the search budget kind when the BudgetSignal
            # is the one that fired, so _stop renders "search rounds" honestly.
            if (
                result.stop_reason is StopReason.STOPPED_BY_BUDGET
                and result.signal_name == "Budget"
            ):
                self.state.budget_exhausted_kind = "search_rounds"
            # WP-3: budget stops with any coverage proceed to draft (resolver decides kind).
            if result.stop_reason is StopReason.STOPPED_BY_BUDGET:
                self.state.transition_to(AgentState.DRAFTING)
            else:
                await self._stop(result.stop_reason)
            return

        self.state.transition_to(AgentState.SEARCHING)

    async def _handle_drafting(self) -> None:
        await draft_answer(self.state)
        # PR-3 Mejora 3.2: emit DraftSynthesized after every STANDARD draft so
        # the event log records the draft + answer_kind independently of the
        # subsequent JudgeRuled / Stopped events (RF-03 auditability).
        payload = self.state.draft_payload
        if payload is not None:
            from app.domain.events import DraftSynthesizedEvent

            await self.emit(
                DraftSynthesizedEvent(
                    prose=payload.prose,
                    answer_kind=payload.answer_kind,
                    citation_count=len(payload.citations),
                    key_point_count=len(payload.key_points),
                    source="standard",
                )
            )
        self.state.transition_to(AgentState.JUDGING)

    async def _handle_judging(self) -> None:
        # WP-5: Pass emit callback for JudgeProviderDegradedEvent
        judge_event = await evaluate_with_judge(self.state, emit_event=self.emit)
        await self.emit(judge_event)
        self.state.last_judge_confidence = judge_event.judge_confidence
        self.state.last_structural_confidence = judge_event.structural_confidence
        self.state.last_coverage = calculate_coverage(self.state)
        self.state.last_agreement = calculate_agreement(
            self.state.evidence,
            expected_experts=self.state.expected_experts or None,
        )
        self.state.judge_attempts += 1

        # IP-25 Phase B: Update confidence history for no-progress detection
        self.state.confidence_history.append(judge_event.final_confidence)

        # IP-25 Phase B: Check for no-progress (confidence plateau)
        from app.domain.events import NoProgressDetectedEvent
        from app.stopping.signals.no_progress import check_no_progress

        fires, delta = await check_no_progress(self.state)
        if (
            fires
            and not self.state.no_progress_triggered
            and self.state.judge_attempts < self.state.max_judge_attempts
        ):
            # Plateau detected — dedupe via flag, emit event, force synthesis
            self.state.no_progress_triggered = True
            await self.emit(
                NoProgressDetectedEvent(
                    delta_3rounds=delta,
                    current_confidence=self.state.confidence_history[-1],
                )
            )
            # Force synthesis-then-finalize path: skip another search/analyze cycle
            self.state.transition_to(AgentState.DRAFTING)
            return

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

        # IP-26 / BRD-26 §4.6: reflective meta-judge runs after every judge
        # ruling on STANDARD/DEEP. It can short-circuit the regular stopping
        # policy into a best-effort stop when continuing is not worth it, or
        # confirm the draft when the adversarial reviewer finds no real gap.
        meta_outcome = await self._maybe_run_meta_judge(judge_event)
        if meta_outcome == "stop_best_effort":
            # PR-6b: meta-judge decided the current best-effort answer is
            # the most we can produce. Per the WP-3 amendment (enums.py)
            # the only positive terminal is JUDGE_CONFIRMED; the
            # "honest, but limited" outcome is wrapped via
            # AnswerKind=BEST_EFFORT inside that terminal.
            self.state.budget_exhausted_kind = "search_rounds"
            try:
                from app.agent.tasks.draft import draft_best_effort_fallback

                await draft_best_effort_fallback(
                    self.state,
                    judge_issues=list(judge_event.suggested_improvements or []),
                )
            except Exception:  # pragma: no cover — never block stop on fallback
                logger.exception(
                    "meta_judge_best_effort_fallback_failed",
                    run_id=str(self.state.run_id),
                )
            await self._stop(StopReason.JUDGE_CONFIRMED)
            return
        if meta_outcome == "confirm":
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
            # PR-1 Mejora 2.1: mark the search budget kind when the BudgetSignal
            # fired (rather than a higher-priority signal that happened to map
            # to STOPPED_BY_BUDGET).
            if (
                result.stop_reason is StopReason.STOPPED_BY_BUDGET
                and result.signal_name == "Budget"
            ):
                self.state.budget_exhausted_kind = "search_rounds"
            # PR-6a: if the judge passed on this very ruling but a layered
            # signal (typically Budget) now says "stop", honour the judge.
            # Throwing away a passing verdict as STOPPED_BY_BUDGET
            # mis-labels a positive terminal as exhaustion.
            stop_reason = result.stop_reason
            if (
                stop_reason is StopReason.STOPPED_BY_BUDGET
                and judge_event.passed
            ):
                stop_reason = StopReason.JUDGE_CONFIRMED
            await self._stop(stop_reason)
            return

        # Judge sub-loop safety net (O-07): not part of the layered policy.
        if self.state.judge_attempts >= self.state.max_judge_attempts:
            # PR-1 Mejora 2.1: explicit budget kind for the rationale.
            self.state.budget_exhausted_kind = "judge_attempts"
            # C3: before stopping with STOPPED_BY_BUDGET, regenerate the
            # surfaced answer as a BEST_EFFORT fallback so the user sees a
            # constructive Spanish reply (what we found, what's missing,
            # how to refine) instead of the rejected draft. O-09 still
            # holds: the stop_reason stays STOPPED_BY_BUDGET — we never
            # silently flip to JUDGE_CONFIRMED here.
            try:
                from app.agent.tasks.draft import draft_best_effort_fallback

                await draft_best_effort_fallback(
                    self.state,
                    judge_issues=list(judge_event.suggested_improvements or []),
                )
            except Exception:  # pragma: no cover — never block stop on fallback
                logger.exception(
                    "best_effort_fallback_failed",
                    run_id=str(self.state.run_id),
                )
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

        # BRD-23 WP-2: deep-fetch escalation for shallow citations.
        # We only attempt it when the judge did NOT pass and flagged at
        # least one claim as supported_but_shallow. Success transitions
        # back to ANALYZING for a fresh judge pass; failure falls through
        # to the normal SEARCHING re-route below.
        shallow_ids = getattr(judge_event, "supported_but_shallow_claim_ids", None)
        if not judge_event.passed and shallow_ids and not self._cancelled:
            from app.agent.tasks.deep_fetch import maybe_deep_fetch
            from app.sources.registry import get_registry

            advanced = await maybe_deep_fetch(
                self.state,
                shallow_ids,
                registry=get_registry(),
                emit=self.emit,
            )
            if advanced and not self._cancelled:
                self.state.transition_to(AgentState.ANALYZING)
                return

        self.state.transition_to(AgentState.SEARCHING)

    async def _maybe_run_meta_judge(
        self, judge_event: Any
    ) -> Literal["stop_best_effort", "confirm", "continue", "skipped"]:
        """Delegate to the shared meta-judge hook (BRD-26 §4.6).

        Kept as a thin wrapper so tests and call sites in this class
        continue to work; the actual decision tree lives in
        :mod:`app.agent.meta_judge_hook` and is shared with the DEEP lane.
        """
        from app.agent.meta_judge_hook import maybe_run_meta_judge

        return await maybe_run_meta_judge(
            self.state, self.emit, judge_event, hook="after_judge"
        )

    async def _maybe_run_before_synth_meta_judge(self) -> bool:
        """Pre-synth meta-judge gate (PR-2, post-2026-05-29 eval).

        Fires at most once per run. Gating conditions:
          - ``before_synth_hook_fired`` flag is False, and
          - either all sub-claims are already resolved (we are about to
            transition to DRAFTING), or evidence_total has crossed
            ``settings.meta_judge_before_synth_min_evidence`` mid-flow.

        Outcomes:
          - ``stop_best_effort``: best-effort draft + stop with
            JUDGE_CONFIRMED (AnswerKind=BEST_EFFORT, PR-6b);
            returns True so the caller exits early.
          - ``continue``: force one more SEARCHING round (only if search
            budget allows); returns True.
          - ``confirm`` / ``skipped``: fall through to regular flow;
            returns False.

        Returns:
            True iff the caller should stop further processing in this
            FSM tick (because a stop was triggered or the FSM was
            transitioned back to SEARCHING by the hook).
        """
        from app.config import settings

        if self.state.before_synth_hook_fired:
            return False
        if not settings.meta_judge_enabled:
            return False
        if self.state.selected_lane == Lane.FAST:
            return False

        about_to_draft = self.state.all_claims_resolved()
        evidence_threshold_hit = (
            len(self.state.evidence)
            >= settings.meta_judge_before_synth_min_evidence
        )
        if not (about_to_draft or evidence_threshold_hit):
            return False

        from app.agent.meta_judge_hook import maybe_run_meta_judge

        self.state.before_synth_hook_fired = True
        outcome = await maybe_run_meta_judge(
            self.state, self.emit, None, hook="before_synthesizing"
        )

        if outcome == "stop_best_effort":
            # PR-6b: same semantics as the post-judge stop_best_effort
            # path. WP-3 collapsed StopReason to 4 values; the honest
            # "this is the best we can do" outcome is JUDGE_CONFIRMED
            # carrying AnswerKind=BEST_EFFORT.
            self.state.budget_exhausted_kind = "search_rounds"
            try:
                from app.agent.tasks.draft import draft_best_effort_fallback

                await draft_best_effort_fallback(self.state, judge_issues=[])
            except Exception:  # pragma: no cover — never block stop on fallback
                logger.exception(
                    "before_synth_meta_judge_best_effort_fallback_failed",
                    run_id=str(self.state.run_id),
                )
            await self._stop(StopReason.JUDGE_CONFIRMED)
            return True

        if outcome == "confirm":
            # PR-2: VoC said "stop searching, draft now". Force DRAFTING
            # even if claims are not all resolved — the meta-judge has
            # decided we have enough evidence to attempt synthesis.
            self.state.transition_to(AgentState.DRAFTING)
            return True

        if outcome == "continue":
            # Force another search round, but only if the budget allows;
            # otherwise let the regular flow proceed to DRAFTING so the run
            # still terminates this tick.
            if self.state.search_count < self.state.max_searches:
                self.state.transition_to(AgentState.SEARCHING)
                return True
            return False

        return False

    async def _check_global_budget(self) -> bool:
        """FSM-independent stop guard (PR-1, post-2026-05-29 eval).

        Runs at the head of every orchestrator loop iteration, BEFORE the phase
        dispatch ``match``. Enforces five caps that none of the existing
        ``StoppingSignal`` plugins can fire when the FSM is stuck cycling
        SEARCHING ↔ ANALYZING with no judge attempts (where most of the
        plugins' inputs are zero):

          1. wall-clock — ``state.wall_clock_max_seconds``
          2. tool calls — count of ``ToolCalled`` events
          3. evidence items — ``len(state.evidence)``
          4. query reformulations — count of ``QueryReformulated`` events
          5. event-level plateau — no progress markers in the trailing window

        On exhaustion: sets ``budget_exhausted_kind``, calls ``_stop`` with
        ``STOPPED_BY_BUDGET`` and returns True so the caller breaks the loop.

        Returns:
            True if a stop was triggered, False otherwise.
        """
        # 1. Wall-clock.
        elapsed = (datetime.now(UTC) - self.state.started_at).total_seconds()
        if elapsed >= self.state.wall_clock_max_seconds:
            self.state.budget_exhausted_kind = "wall_clock"
            logger.warning(
                "global_budget_wall_clock_exceeded",
                run_id=str(self.state.run_id),
                elapsed_s=elapsed,
                cap_s=self.state.wall_clock_max_seconds,
            )
            await self._stop(StopReason.STOPPED_BY_BUDGET)
            return True

        # 2. Tool calls (count from the in-memory event log).
        tool_calls = sum(
            1 for ev in self.state.events if ev.type.value == "ToolCalled"
        )
        if tool_calls >= self.state.max_tool_calls_per_run:
            self.state.budget_exhausted_kind = "tool_calls"
            logger.warning(
                "global_budget_tool_calls_exceeded",
                run_id=str(self.state.run_id),
                tool_calls=tool_calls,
                cap=self.state.max_tool_calls_per_run,
            )
            await self._stop(StopReason.STOPPED_BY_BUDGET)
            return True

        # 3. Evidence items.
        if len(self.state.evidence) >= self.state.max_evidence_per_run:
            self.state.budget_exhausted_kind = "evidence"
            logger.warning(
                "global_budget_evidence_exceeded",
                run_id=str(self.state.run_id),
                evidence=len(self.state.evidence),
                cap=self.state.max_evidence_per_run,
            )
            await self._stop(StopReason.STOPPED_BY_BUDGET)
            return True

        # 4. Query reformulations.
        reforms = sum(
            1 for ev in self.state.events if ev.type.value == "QueryReformulated"
        )
        if reforms >= self.state.max_query_reformulations_per_run:
            self.state.budget_exhausted_kind = "query_reformulations"
            logger.warning(
                "global_budget_reformulations_exceeded",
                run_id=str(self.state.run_id),
                reformulations=reforms,
                cap=self.state.max_query_reformulations_per_run,
            )
            await self._stop(StopReason.STOPPED_BY_BUDGET)
            return True

        # 5. Event-level plateau (delegated to no_progress helper).
        from app.stopping.signals.no_progress import (
            check_claim_coverage_plateau,
            check_event_level_plateau,
        )

        if check_event_level_plateau(self.state):
            self.state.budget_exhausted_kind = "no_progress_events"
            logger.warning(
                "global_budget_event_plateau_detected",
                run_id=str(self.state.run_id),
                window=self.state.no_progress_event_window,
                total_events=len(self.state.events),
            )
            await self._stop(StopReason.STOPPED_BY_BUDGET)
            return True

        # 6. PR-5 Mejora 5.2: claim-coverage plateau (3 consecutive analyze
        # rounds with zero new covered claims). Independent of judge runs
        # and of the structural confidence history.
        if check_claim_coverage_plateau(self.state):
            self.state.budget_exhausted_kind = "claim_coverage_plateau"
            logger.warning(
                "global_budget_claim_coverage_plateau_detected",
                run_id=str(self.state.run_id),
                coverage_history=list(self.state.coverage_history),
            )
            await self._stop(StopReason.STOPPED_BY_BUDGET)
            return True

        return False

    async def _handle_error(self, exc: BaseException) -> StopReason:
        error_code: str | None = None
        error_message = str(exc)
        if isinstance(exc, LLMProviderQuotaExhausted) or isinstance(
            exc.__cause__, LLMProviderQuotaExhausted
        ):
            quota_exc = exc if isinstance(exc, LLMProviderQuotaExhausted) else exc.__cause__
            assert isinstance(quota_exc, LLMProviderQuotaExhausted)
            error_code = "llm_provider_quota_exhausted"
            error_message = (
                f"LLM provider '{quota_exc.provider}' returned a quota-exhausted "
                f"error. The run cannot continue with this provider until the "
                f"quota resets. Try another provider or wait."
            )
        elif isinstance(exc, LLMPoolExhausted) or isinstance(
            exc.__cause__, LLMPoolExhausted
        ):
            error_code = "llm_pool_rate_limited"
        logger.error(
            "agent_run_error",
            run_id=str(self.state.run_id),
            error_type=type(exc).__name__,
            error_message=str(exc),
            error_code=error_code,
        )
        await self.emit(
            AgentErroredEvent(
                error_type=type(exc).__name__,
                error_message=error_message,
                stack_trace=traceback.format_exc(),
                recoverable=False,
                recovery_suggestion=None,
                error_code=error_code,
            )
        )
        return await self._stop(StopReason.ERRORED)

    async def _stop(self, reason: StopReason) -> StopReason:
        """Transition to terminal state and emit StoppedEvent with StopRationale (WP-3 G2)."""
        self.state.stop_reason = reason
        if self.state.current_state not in (AgentState.STOPPED, AgentState.ERRORED):
            target = AgentState.ERRORED if reason == StopReason.ERRORED else AgentState.STOPPED
            self.state.transition_to(target)
        # WP-3 (IP-21) Always-Answer: surface the latest draft whenever one
        # exists, even when the run hits the budget without judge confirmation.
        surfaces_draft = reason in (
            StopReason.JUDGE_CONFIRMED,
            StopReason.STOPPED_BY_BUDGET,
        )
        answer = self.state.draft_answer if surfaces_draft else None
        answer_structured: str | None = None
        answer_structured_data = None
        answer_kind = self.state.selected_answer_kind if surfaces_draft else None

        # BRD-16: render BOTH formats at stop time for client-side switching
        if surfaces_draft and answer:
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
                synth_payload=self.state.draft_payload,
            )
            # Always render prose as the canonical answer_prose
            prose_renderer = renderer_registry.get("prose") or renderer_registry.get_default()
            answer = prose_renderer.render(render_ctx).content

            # Render structured (markdown legacy + typed JSON data for the FE)
            struct_renderer = renderer_registry.get("structured") or renderer_registry.get_default()
            structured_output = struct_renderer.render(render_ctx)
            answer_structured = structured_output.content
            # The StructuredRenderer puts the typed payload under metadata["data"].
            if hasattr(struct_renderer, "build_data"):
                try:
                    answer_structured_data = struct_renderer.build_data(render_ctx)
                except Exception:  # pragma: no cover — never block stop on rendering
                    answer_structured_data = None

        if surfaces_draft and answer:
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
            # PR-1 Mejora 2.1: prefer the explicit budget_exhausted_kind set by
            # the lane / policy. Fall back to inference for back-compat with
            # paths that have not yet been wired.
            kind = self.state.budget_exhausted_kind
            if kind is None:
                if self.state.judge_attempts >= self.state.max_judge_attempts:
                    kind = "judge_attempts"
                elif self.state.selected_lane == Lane.DEEP:
                    kind = "react_steps"
                else:
                    kind = "search_rounds"
            if kind == "judge_attempts":
                budget_summary = (
                    f"Judge rejected the draft after "
                    f"{self.state.judge_attempts} attempts"
                )
                budget_signal = "judge_cap"
            elif kind == "react_steps":
                budget_summary = (
                    f"Reached ReAct step limit "
                    f"({self.state.react_step_count}/{self.state.max_react_steps} steps)"
                )
                budget_signal = "budget"
            elif kind == "wall_clock":
                elapsed = (
                    datetime.now(UTC) - self.state.started_at
                ).total_seconds()
                budget_summary = (
                    f"Reached wall-clock limit "
                    f"({elapsed:.0f}/{self.state.wall_clock_max_seconds}s)"
                )
                budget_signal = "budget"
            elif kind == "tool_calls":
                tool_calls = sum(
                    1 for ev in self.state.events
                    if ev.type.value == "ToolCalled"
                )
                budget_summary = (
                    f"Reached tool-call limit "
                    f"({tool_calls}/{self.state.max_tool_calls_per_run} calls)"
                )
                budget_signal = "budget"
            elif kind == "evidence":
                budget_summary = (
                    f"Reached evidence limit "
                    f"({len(self.state.evidence)}/{self.state.max_evidence_per_run} items)"
                )
                budget_signal = "budget"
            elif kind == "query_reformulations":
                reforms = sum(
                    1 for ev in self.state.events
                    if ev.type.value == "QueryReformulated"
                )
                budget_summary = (
                    f"Reached query-reformulation limit "
                    f"({reforms}/{self.state.max_query_reformulations_per_run} reformulations)"
                )
                budget_signal = "budget"
            elif kind == "no_progress_events":
                budget_summary = (
                    f"No structural progress in the last "
                    f"{self.state.no_progress_event_window} events"
                )
                budget_signal = "no_progress"
            elif kind == "claim_coverage_plateau":
                budget_summary = (
                    f"No new claim coverage in the last 3 analyze rounds "
                    f"(covered: {len(self.state.covered_claims)}/"
                    f"{len(self.state.sub_claims)})"
                )
                budget_signal = "no_progress"
            else:  # search_rounds
                budget_summary = (
                    f"Reached search limit "
                    f"({self.state.search_count}/{self.state.max_searches} rounds)"
                )
                budget_signal = "budget"
            # PR-1 Mejora 2.2: when the judge never confirmed but we have a
            # structural confidence S, surface it as a best-effort score with
            # the discriminator so the UI distinguishes it from a judge score.
            if self.state.last_judge_confidence is not None:
                rationale_confidence = self.state.last_judge_confidence
                confidence_kind: Literal["judge", "structural"] | None = "judge"
            elif self.state.last_structural_confidence is not None:
                rationale_confidence = self.state.last_structural_confidence
                confidence_kind = "structural"
            else:
                rationale_confidence = None
                confidence_kind = None
            stop_rationale = StopRationale(
                reason=reason,
                triggering_signal=budget_signal,
                summary=budget_summary,
                confidence=rationale_confidence,
                confidence_kind=confidence_kind,
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
                answer_structured_data=answer_structured_data,
                answer_kind=answer_kind,
                stop_rationale=stop_rationale,
                total_tokens=self.state.total_tokens,
            )
        )

        # BRD-22 Phase 6: Record to instant cache when JUDGE_CONFIRMED with judge_confidence
        if (
            reason == StopReason.JUDGE_CONFIRMED
            and self.state.last_judge_confidence is not None
            and self.state.owner_username
            and not getattr(self, "_from_cache_replay", False)
        ):
            from app.agent.instant_cache import CachedRun, record_run

            cached_payload = CachedRun(
                run_id=self.state.run_id,
                final_confidence=self.state.last_judge_confidence,
                judge_confidence=self.state.last_judge_confidence,
                structural_confidence=self.state.last_structural_confidence,
                stop_reason=reason,
                answer_kind=answer_kind,
                answer_prose=answer,
                answer_structured=answer_structured,
                answer_structured_data=(
                    answer_structured_data.model_dump(mode="json")
                    if answer_structured_data is not None
                    else None
                ),
                citations=None,  # TODO: extract from evidence or state if available
                completed_at=datetime.now(UTC),
            )
            record_run(
                self.state.owner_username,
                self.state.question,
                cached_payload,
            )

        logger.info(
            "agent_run_complete",
            run_id=str(self.state.run_id),
            stop_reason=reason.value,
            iterations=self.state.iteration_count,
        )
        return reason

    async def _stop_from_cache(self, cached: Any) -> StopReason:
        """Replay a cached answer by emitting synthetic events.

        BRD-22 Phase 6: Emit PriorRunHintReplayedEvent, synthetic JudgeRuledEvent,
        and StoppedEvent with triggering_signal="instant_cache". Sets internal
        flag to prevent re-caching the replayed run.

        Args:
            cached: CachedRun instance from instant_cache.try_replay.

        Returns:
            StopReason.JUDGE_CONFIRMED.
        """

        from app.agent.instant_cache import CachedRun, normalise_question
        from app.domain.events import JudgeRuledEvent, PriorRunHintReplayedEvent

        # Type guard
        if not isinstance(cached, CachedRun):
            raise TypeError(f"Expected CachedRun, got {type(cached)}")

        # Set flag to prevent re-caching this replayed run
        self._from_cache_replay = True

        # Emit PriorRunHintReplayedEvent
        await self.emit(
            PriorRunHintReplayedEvent(
                source_run_id=cached.run_id,
                source_final_confidence=cached.final_confidence,
                source_stop_reason=cached.stop_reason,
                source_answer_kind=cached.answer_kind,
                normalised_question=normalise_question(self.state.question),
                prior_completed_at=cached.completed_at,
            )
        )

        # Emit synthetic JudgeRuledEvent carrying prior confidence and answer fields
        await self.emit(
            JudgeRuledEvent(
                judge_model="replayed",
                judge_confidence=cached.judge_confidence or cached.final_confidence,
                structural_confidence=cached.structural_confidence or cached.final_confidence,
                final_confidence=cached.final_confidence,
                threshold=self.state.confidence_threshold,
                passed=True,
                rationale="Replayed from instant cache",
                answer_kind=cached.answer_kind,
            )
        )

        # Update state for terminal fields
        self.state.last_judge_confidence = cached.judge_confidence or cached.final_confidence
        self.state.last_structural_confidence = cached.structural_confidence or cached.final_confidence
        self.state.selected_answer_kind = cached.answer_kind
        self.state.final_answer = cached.answer_prose

        # Build StoppedEvent with triggering_signal="instant_cache"
        stop_rationale = StopRationale(
            reason=StopReason.JUDGE_CONFIRMED,
            triggering_signal="instant_cache",
            summary=f"Replayed from cache with confidence {cached.final_confidence:.2f}",
            confidence=cached.final_confidence,
        )

        self.state.stop_reason = StopReason.JUDGE_CONFIRMED
        self.state.transition_to(AgentState.STOPPED)

        await self.emit(
            StoppedEvent(
                stop_reason=StopReason.JUDGE_CONFIRMED,
                answer_prose=cached.answer_prose,
                answer_structured=cached.answer_structured,
                answer_structured_data=cached.answer_structured_data,
                answer_kind=cached.answer_kind,
                stop_rationale=stop_rationale,
                total_tokens=self.state.total_tokens,
            )
        )

        logger.info(
            "agent_run_cache_replay",
            run_id=str(self.state.run_id),
            source_run_id=str(cached.run_id),
            final_confidence=cached.final_confidence,
        )

        return StopReason.JUDGE_CONFIRMED

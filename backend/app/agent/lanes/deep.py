"""DEEP lane execution (IP-25 Phase E+F).

Abductive reasoning via ReAct loop for causal/scenario/deep questions.
Flow: generate hypotheses → ReAct loop → synthesize → CoVe → judge.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog

from app.agent.react.loop import run_react_loop
from app.agent.run_state import RunState
from app.agent.tasks.hypotheses import generate_hypotheses
from app.agent.tasks.select_answer_kind import AnswerKindInputs, select_answer_kind
from app.domain.enums import AnswerKind, QuestionType, StopReason
from app.domain.events import (
    BaseEvent,
    DraftSynthesizedEvent,
    HypothesesGeneratedEvent,
)
from app.llm import LLMRole, llm
from app.llm.models import SynthesizedAnswer

logger = structlog.get_logger(__name__)


async def execute_deep_lane(
    state: RunState,
    emit: Callable[[BaseEvent], Awaitable[None]],
) -> StopReason:
    """Execute DEEP lane pipeline: hypotheses → ReAct → synth → CoVe → judge.

    Args:
        state: RunState instance with question already normalized and classified
        emit: Async callable for emitting events

    Returns:
        StopReason (JUDGE_CONFIRMED or STOPPED_BY_BUDGET)

    Logic:
        1. Generate hypotheses if not already present (reuses Phase D)
        2. Run ReAct loop (up to max_react_steps, typically 8)
        3. If loop returns "forced_synth" or STOPPED_BY_BUDGET:
           - Call synthesizer with react_history as context
           - Run CoVe (Chain-of-Verification): generate 3 questions,
             verify each, and re-draft if contradictions found and
             cove_rounds < max_cove_rounds (Phase F)
           - Call mini-judge (simplified judge for DEEP in V1)
           - Return judge result
        4. If loop returns other StopReason (e.g., JUDGE_CONFIRMED):
           - Return that reason directly

    Mutations:
        - Populates state.hypotheses (if empty)
        - Populates state.react_history via run_react_loop
        - Sets state.draft_answer on synthesis
        - Increments state.cove_rounds if re-draft occurs
        - Sets state.final_answer on judge confirmation
    """
    logger.info(
        "deep_lane_starting",
        run_id=str(state.run_id),
        question_type=state.question_type,
    )

    # Step 1: Generate hypotheses if needed
    if not state.hypotheses:
        logger.info(
            "deep_lane_generating_hypotheses",
            run_id=str(state.run_id),
        )
        hypotheses = await generate_hypotheses(state)
        state.hypotheses = hypotheses

        await emit(
            HypothesesGeneratedEvent(
                hypotheses=[h.model_dump() for h in hypotheses],  # type: ignore[arg-type]
            )
        )

    # PR-4 Mejora 4.1: stamp the resolver-chosen AnswerKind on the RunState
    # before the ReAct loop so every downstream consumer (meta-judge ctx,
    # StoppedEvent, structured renderer) sees a non-null value even when the
    # run is best-effort stopped before any draft is synthesised (G15/Q7).
    if state.selected_answer_kind is None:
        state.selected_answer_kind = _select_deep_answer_kind(state)

    # Step 2: Run ReAct loop
    logger.info(
        "deep_lane_react_loop_starting",
        run_id=str(state.run_id),
        hypotheses_count=len(state.hypotheses),
    )

    react_result = await run_react_loop(state, emit, max_steps=state.max_react_steps)

    logger.info(
        "deep_lane_react_loop_completed",
        run_id=str(state.run_id),
        result=react_result,
        steps_executed=state.react_step_count,
    )

    # Step 3: Handle loop result
    if react_result == "forced_synth" or react_result == StopReason.STOPPED_BY_BUDGET:
        # Need to synthesize with best effort
        logger.info(
            "deep_lane_synthesizing_best_effort",
            run_id=str(state.run_id),
        )

        draft = await _synthesize_with_react_history(state)
        draft_text = draft.prose
        state.draft_answer = draft_text
        state.draft_payload = draft
        await emit(
            DraftSynthesizedEvent(
                prose=draft.prose,
                answer_kind=draft.answer_kind,
                citation_count=len(draft.citations),
                key_point_count=len(draft.key_points),
                source="deep_react",
            )
        )

        # Phase F: Chain-of-Verification (CoVe)
        logger.info(
            "deep_lane_cove_starting",
            run_id=str(state.run_id),
            cove_rounds=state.cove_rounds,
        )

        # Import CoVe functions
        from app.agent.tasks.cove import (
            generate_verification_questions,
            get_registry,
            verify_question,
        )
        from app.domain.events import (
            CoveContradictionDetectedEvent,
            VerificationQuestionsGeneratedEvent,
        )

        # Generate verification questions
        questions = await generate_verification_questions(draft_text)
        await emit(VerificationQuestionsGeneratedEvent(questions=questions))

        # Verify each question
        contradictions: list[tuple[str, str]] = []
        registry = get_registry()

        for question in questions:
            if not question.strip():
                continue
            verdict = await verify_question(question, draft_text, registry)
            if verdict.contradicts:
                await emit(
                    CoveContradictionDetectedEvent(
                        question=question,
                        contradicting_evidence=verdict.evidence,
                    )
                )
                contradictions.append((question, verdict.evidence))

        # Re-draft if contradictions found and budget allows
        if contradictions and state.cove_rounds < state.max_cove_rounds:
            logger.info(
                "deep_lane_cove_redrafting",
                run_id=str(state.run_id),
                contradiction_count=len(contradictions),
            )
            state.cove_rounds += 1

            # Build contradiction context
            contradiction_context = "\n\n".join(
                f"Verification question: {q}\nContradicting evidence: {e}"
                for q, e in contradictions
            )

            # Re-synthesize with contradictions as context
            redraft = await _synthesize_with_contradictions(
                state, contradiction_context
            )
            draft_text = redraft.prose
            state.draft_answer = draft_text
            state.draft_payload = redraft
            await emit(
                DraftSynthesizedEvent(
                    prose=redraft.prose,
                    answer_kind=redraft.answer_kind,
                    citation_count=len(redraft.citations),
                    key_point_count=len(redraft.key_points),
                    source="deep_cove",
                )
            )

            logger.info(
                "deep_lane_cove_redraft_complete",
                run_id=str(state.run_id),
                cove_rounds=state.cove_rounds,
            )
        else:
            if contradictions:
                logger.info(
                    "deep_lane_cove_budget_exhausted",
                    run_id=str(state.run_id),
                    contradiction_count=len(contradictions),
                )
            else:
                logger.info(
                    "deep_lane_cove_no_contradictions",
                    run_id=str(state.run_id),
                )

        # BRD-26 §4.6: reflective meta-judge on DEEP runs at the
        # ``after_cove`` hook, right before the mini-judge. It can short-
        # circuit the mini-judge into a best-effort stop or confirm the
        # current draft when adversarial completeness finds no real gap.
        from app.agent.meta_judge_hook import maybe_run_meta_judge

        class _CoveSignal:
            __slots__ = (
                "passed",
                "judge_confidence",
                "structural_confidence",
                "final_confidence",
                "rationale",
                "suggested_improvements",
            )

            def __init__(self) -> None:
                self.passed = False
                self.judge_confidence = state.last_judge_confidence or 0.0
                self.structural_confidence = state.last_structural_confidence or 0.0
                self.final_confidence = min(
                    self.judge_confidence, self.structural_confidence
                )
                self.rationale = (
                    "after_cove pre-judge: no judge ruling yet on this draft"
                )
                self.suggested_improvements: list[str] = []

        meta_outcome = await maybe_run_meta_judge(
            state, emit, _CoveSignal(), hook="after_cove"
        )
        if meta_outcome == "stop_best_effort":
            state.final_answer = draft_text
            state.budget_exhausted_kind = "react_steps"
            _ensure_deep_structural_confidence(state)
            logger.info(
                "deep_lane_meta_judge_best_effort_stop",
                run_id=str(state.run_id),
            )
            return StopReason.STOPPED_BY_BUDGET
        if meta_outcome == "confirm":
            state.final_answer = draft_text
            state.last_judge_confidence = state.last_judge_confidence or 0.0
            logger.info(
                "deep_lane_meta_judge_confirmed",
                run_id=str(state.run_id),
            )
            return StopReason.JUDGE_CONFIRMED

        # Mini-judge: simplified judge for V1 DEEP lane.
        # FAST_MINI_JUDGE_PROMPT has no {} placeholders — the question/answer
        # must travel in the user message, mirroring the fast lane pattern.
        from app.llm.models import MiniJudgeVerdict
        from app.llm.prompts import FAST_MINI_JUDGE_PROMPT

        judge_response = await llm.call(
            role=LLMRole.JUDGE,
            messages=[
                {"role": "system", "content": FAST_MINI_JUDGE_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Question: {state.question}\n\n"
                        f"Answer: {draft_text}\n\n"
                        "Sources: (see citations embedded in the answer above)"
                    ),
                },
            ],
            response_model=MiniJudgeVerdict,
        )

        if judge_response.ok:
            state.final_answer = draft_text
            state.last_judge_confidence = judge_response.j_score
            logger.info(
                "deep_lane_judge_confirmed",
                run_id=str(state.run_id),
                confidence=judge_response.j_score,
            )
            return StopReason.JUDGE_CONFIRMED
        else:
            # Judge rejected, but we've exhausted budget.
            # PR-1 Mejora 2.1: mark the actual budget that fired so _stop
            # reports "ReAct step limit" instead of "search limit (0 rounds)".
            state.final_answer = draft_text
            state.budget_exhausted_kind = "react_steps"
            _ensure_deep_structural_confidence(state)
            logger.info(
                "deep_lane_stopped_by_budget",
                run_id=str(state.run_id),
            )
            return StopReason.STOPPED_BY_BUDGET

    # react_result is a StopReason
    # Loop returned a definitive stop reason
    logger.info(
        "deep_lane_stopped_by_react_signal",
        run_id=str(state.run_id),
        stop_reason=react_result,
    )

    # If JUDGE_CONFIRMED, still need to synthesize
    if react_result == StopReason.JUDGE_CONFIRMED:
        draft = await _synthesize_with_react_history(state)
        state.draft_answer = draft.prose
        state.draft_payload = draft
        state.final_answer = draft.prose
        await emit(
            DraftSynthesizedEvent(
                prose=draft.prose,
                answer_kind=draft.answer_kind,
                citation_count=len(draft.citations),
                key_point_count=len(draft.key_points),
                source="deep_react",
            )
        )

    return react_result


async def _synthesize_with_react_history(state: RunState) -> SynthesizedAnswer:
    """Synthesize answer using ReAct history as context.

    PR-3 Mejora 3.1: route through ``build_synthesizer_prompt`` with an
    ``answer_kind`` selected by the deterministic resolver, instead of the
    minimalistic ``FAST_SYNTH_PROMPT``. ReAct observations are folded into
    the evidence list so they reach the synthesizer in the same shape as
    STANDARD-lane evidence (URL/title/snippet) plus a synthetic ReAct entry
    that preserves the step-by-step trail.
    """
    from app.llm.prompts import build_synthesizer_prompt

    answer_kind = _select_deep_answer_kind(state)

    evidence_list = _build_deep_evidence_list(state)
    hypotheses_list = _build_hypotheses_list(state)

    system_prompt, max_tokens = build_synthesizer_prompt(
        question=state.question,
        evidence=evidence_list,
        answer_kind=answer_kind,
        user_language="es",
        hypotheses=hypotheses_list,
    )

    synth_response = await llm.call(
        role=LLMRole.SYNTHESIZER,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state.question},
        ],
        response_model=SynthesizedAnswer,
        max_tokens=max_tokens,
    )

    # Stamp the resolver-chosen kind so downstream renderers and audit events
    # see a consistent answer_kind even when the model omits it.
    if synth_response.answer_kind is None:
        synth_response.answer_kind = answer_kind

    return synth_response


async def _synthesize_with_contradictions(
    state: RunState,
    contradiction_context: str,
) -> SynthesizedAnswer:
    """Re-synthesize answer addressing CoVe contradictions.

    Args:
        state: Current run state with react_history
        contradiction_context: Formatted string with contradicting evidence

    Returns:
        New synthesized answer addressing contradictions
    """
    from app.llm.prompts import build_synthesizer_prompt

    answer_kind = _select_deep_answer_kind(state, contradictions_present=True)

    evidence_list = _build_deep_evidence_list(state)
    # Append contradictions as an extra synthetic evidence item so the
    # synthesizer surfaces them in the resulting prose.
    evidence_list.append(
        {
            "url": "internal://cove/contradictions",
            "title": "Verification contradictions",
            "snippet": contradiction_context,
        }
    )
    hypotheses_list = _build_hypotheses_list(state)

    system_prompt, max_tokens = build_synthesizer_prompt(
        question=state.question,
        evidence=evidence_list,
        answer_kind=answer_kind,
        user_language="es",
        requires_contradictions=True,
        hypotheses=hypotheses_list,
    )

    synth_response = await llm.call(
        role=LLMRole.SYNTHESIZER,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state.question},
        ],
        response_model=SynthesizedAnswer,
        max_tokens=max_tokens,
    )

    if synth_response.answer_kind is None:
        synth_response.answer_kind = answer_kind

    return synth_response


def _build_deep_evidence_list(state: RunState) -> list[dict]:
    """Format state.evidence + the ReAct trail as synthesizer evidence rows."""
    items: list[dict] = [
        {
            "url": e.source_url,
            "title": e.source_title,
            "snippet": e.text,
        }
        for e in state.evidence
    ]
    history_lines = [
        f"Step {step.step}: {step.thought} | Action: {step.action.type} "
        f"| Result: {step.observation[:200]}"
        for step in state.react_history
        if step.step >= 0
    ]
    if history_lines:
        items.append(
            {
                "url": "internal://react/history",
                "title": "ReAct loop trace",
                "snippet": "\n".join(history_lines),
            }
        )
    return items


def _build_hypotheses_list(state: RunState) -> list[dict] | None:
    if not state.hypotheses:
        return None
    return [
        {"text": h.text, "priority": h.priority} for h in state.hypotheses
    ]


def _select_deep_answer_kind(
    state: RunState,
    *,
    contradictions_present: bool = False,
) -> AnswerKind:
    """Pick the DEEP-lane answer kind via the shared deterministic resolver.

    Hypothesis coverage drives ``coverage``: it counts the fraction of
    hypotheses whose verdict is no longer ``pending``. Agreement is lowered
    when CoVe contradictions surfaced so the resolver leans toward
    ``BEST_EFFORT``/``WEIGHTED`` instead of ``DIRECT``.
    """
    question_type = state.question_type or QuestionType.STATE_OF_ART
    total_hypotheses = len(state.hypotheses) or 0
    resolved = sum(
        1 for h in state.hypotheses if h.verdict in ("confirmed", "refuted")
    )
    coverage = (resolved / total_hypotheses) if total_hypotheses else 0.0
    agreement = 0.4 if contradictions_present else 0.8
    return select_answer_kind(
        AnswerKindInputs(
            question_type=question_type,
            structural_confidence=state.last_structural_confidence or 0.0,
            coverage=coverage,
            agreement=agreement,
            ambiguity_flag=state.has_ambiguity,
        )
    )


def _ensure_deep_structural_confidence(state: RunState) -> None:
    """PR-4 Mejora 4.2: guarantee ``last_structural_confidence`` is populated
    on best-effort DEEP stops so ``StopRationale.confidence`` is non-null and
    the UI surfaces a real score (or "Best-effort") instead of 0 %.
    """
    if state.last_structural_confidence is not None:
        return
    from app.confidence import calculate_structural_confidence

    try:
        state.last_structural_confidence = calculate_structural_confidence(state).score
    except Exception:  # pragma: no cover - never block stop on confidence calc
        logger.exception(
            "deep_lane_structural_confidence_failed",
            run_id=str(state.run_id),
        )

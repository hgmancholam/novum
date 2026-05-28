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
from app.domain.enums import StopReason
from app.domain.events import BaseEvent, HypothesesGeneratedEvent
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

        # Mini-judge: simplified judge for V1 DEEP lane
        from app.llm.models import MiniJudgeVerdict
        from app.llm.prompts import FAST_MINI_JUDGE_PROMPT

        judge_response = await llm.call(
            role=LLMRole.JUDGE,
            messages=[
                {
                    "role": "system",
                    "content": FAST_MINI_JUDGE_PROMPT.format(
                        question=state.question,
                        answer=draft_text,
                    ),
                },
                {"role": "user", "content": "Evaluate this answer."},
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
            # Judge rejected, but we've exhausted budget
            state.final_answer = draft_text
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
        state.final_answer = draft.prose

    return react_result


async def _synthesize_with_react_history(state: RunState) -> SynthesizedAnswer:
    """Synthesize answer using ReAct history as context."""
    # Build context from react_history
    history_context = "\n".join(
        f"Step {step.step}: {step.thought}\nAction: {step.action.type}\nResult: {step.observation[:200]}..."
        for step in state.react_history
        if step.step >= 0  # Exclude synthetic summary steps (step=-1)
    )

    hypotheses_context = "\n".join(
        f"- [{h.verdict.upper()}] {h.text}"
        for h in state.hypotheses
    )

    from app.llm.prompts import FAST_SYNTH_PROMPT

    synth_response = await llm.call(
        role=LLMRole.SYNTHESIZER,
        messages=[
            {
                "role": "system",
                "content": FAST_SYNTH_PROMPT.format(
                    question=state.question,
                    evidence="See ReAct loop history below",
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {state.question}\n\n"
                    f"Hypotheses:\n{hypotheses_context}\n\n"
                    f"ReAct History:\n{history_context}\n\n"
                    f"Synthesize a concise answer (2-3 sentences)."
                ),
            },
        ],
        response_model=SynthesizedAnswer,
    )

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
    # Build context from react_history
    history_context = "\n".join(
        f"Step {step.step}: {step.thought}\nAction: {step.action.type}\nResult: {step.observation[:200]}..."
        for step in state.react_history
        if step.step >= 0  # Exclude synthetic summary steps (step=-1)
    )

    hypotheses_context = "\n".join(
        f"- [{h.verdict.upper()}] {h.text}" for h in state.hypotheses
    )

    from app.llm.prompts import FAST_SYNTH_PROMPT

    synth_response = await llm.call(
        role=LLMRole.SYNTHESIZER,
        messages=[
            {
                "role": "system",
                "content": FAST_SYNTH_PROMPT.format(
                    question=state.question,
                    evidence="See ReAct loop history and verification contradictions below",
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {state.question}\n\n"
                    f"Hypotheses:\n{hypotheses_context}\n\n"
                    f"ReAct History:\n{history_context}\n\n"
                    f"CONTRADICTIONS DETECTED:\n{contradiction_context}\n\n"
                    f"Synthesize a revised answer (2-3 sentences) that addresses the contradictions."
                ),
            },
        ],
        response_model=SynthesizedAnswer,
    )

    return synth_response

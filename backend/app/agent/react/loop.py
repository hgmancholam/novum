"""ReAct loop implementation (IP-25 Phase E T-25-E-03).

Core Thought-Action-Observation cycle for DEEP lane hypothesis evaluation.
Integrates with Source seam, emits 3 events per step, checks intra-loop
stopping signals, and handles invalid actions with retry budget.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

import structlog
from pydantic import BaseModel

from app.agent.meta_judge_hook import maybe_run_meta_judge
from app.agent.react.actions import (
    AgentActionUnion,
    DeepFetchAction,
    EvaluateHypothesisAction,
    FinishAction,
    SearchAction,
)
from app.agent.react.history import ReactStep, summarize_history_if_needed
from app.agent.run_state import EvidenceItem, RunState
from app.config import settings
from app.domain.enums import EvidencePolarity, StopReason
from app.domain.events import (
    AgentActionEvent,
    AgentObservationEvent,
    AgentThoughtEvent,
    BaseEvent,
    EvidenceAddedEvent,
    HistorySummarizedEvent,
    HypothesisEvaluatedEvent,
    ToolCalledEvent,
)
from app.llm import LLMRole, llm
from app.seams.source import SourceResult
from app.sources.registry import SourceRegistry, get_registry

logger = structlog.get_logger(__name__)

_MAX_RETRIES_PER_STEP = 3
_MAX_RESULTS_PER_SEARCH = 5


class ThoughtOutput(BaseModel):
    """LLM structured output for thought generation."""

    thought: str


@dataclass(frozen=True)
class _ReactJudgeSignal:
    """Duck-typed `judge_signal` for `maybe_run_meta_judge` (BRD-26 §4.13).

    No real judge ruling exists mid-ReAct, so we synthesize one from the
    latest evidence-derived proxies and the most recent observation.
    Mirrors the contract used by the orchestrator's `after_judge` hook.
    """

    passed: bool
    structural_confidence: float
    judge_confidence: float
    final_confidence: float
    rationale: str


def _synthetic_signal_from_react(state: RunState) -> _ReactJudgeSignal:
    structural = state.last_structural_confidence or 0.0
    judge = state.last_judge_confidence or 0.0
    if state.react_history:
        rationale = str(state.react_history[-1].observation)[:280]
    else:
        rationale = "no_observations_yet"
    return _ReactJudgeSignal(
        passed=False,
        structural_confidence=structural,
        judge_confidence=judge,
        final_confidence=min(structural, judge),
        rationale=rationale,
    )


def _cost_gate_after_react_ok(state: RunState) -> bool:
    """BRD-26 §4.13 activation predicate for `after_react_observation`.

    All conditions must hold; the global `meta_judge_enabled` kill-switch
    is checked first so callers can rely on this single function.
    """
    if not settings.meta_judge_enabled:
        return False
    if not settings.meta_judge_after_react_enabled:
        return False
    if state.react_step_count < settings.meta_judge_react_warmup_steps:
        return False
    return state.meta_judge_calls < settings.max_meta_judge_calls_per_run


async def run_react_loop(
    state: RunState,
    emit: Callable[[BaseEvent], Awaitable[None]],
    max_steps: int = 8,
) -> StopReason | Literal["forced_synth"]:
    """Execute ReAct loop: Thought → Action → Observation → Check stopping.

    Args:
        state: Current run state with hypotheses populated
        emit: Event emission callback
        max_steps: Maximum number of steps before forcing synthesis (default 8)

    Returns:
        StopReason if a terminal condition is met, "forced_synth" if step cap hit

    Logic per step:
        1. Thought: LLM call with REACT_THOUGHT_PROMPT showing history + hypotheses
        2. Action: LLM call with structured output (AgentActionUnion)
        3. Execute action: dispatch on action.type
           - SearchAction → Source.search → EvidenceAddedEvent
           - DeepFetchAction → Source.fetch_full → EvidenceAddedEvent
           - EvaluateHypothesisAction → update state.hypotheses[idx]
           - FinishAction → return appropriate StopReason or forced_synth
        4. Emit: AgentThoughtEvent, AgentActionEvent, AgentObservationEvent
        5. Check intra-loop stopping signals (HypothesisConfirmed, AllRefuted, etc.)
        6. Invalid actions: log warning, retry up to 3 times without counting step
        7. After loop: summarize_history_if_needed if tokens > 15k

    Mutations:
        - Appends to state.react_history
        - Increments state.react_step_count
        - May update state.hypotheses[].verdict and evidence_ids
        - Adds evidence to state.evidence
    """
    logger.info(
        "react_loop_starting",
        run_id=str(state.run_id),
        max_steps=max_steps,
        hypotheses_count=len(state.hypotheses),
    )

    registry = get_registry()
    step = 0
    invalid_action_retries = 0

    while step < max_steps:
        # Step 1: Generate thought
        thought = await _generate_thought(state)

        # Step 2: Generate action
        try:
            action = await _generate_action(state, thought)
        except Exception as exc:
            logger.warning(
                "react_action_generation_failed",
                step=step,
                error=str(exc),
                run_id=str(state.run_id),
            )
            invalid_action_retries += 1
            if invalid_action_retries >= _MAX_RETRIES_PER_STEP:
                logger.error(
                    "react_action_retry_budget_exhausted",
                    step=step,
                    run_id=str(state.run_id),
                )
                break
            continue  # Retry without incrementing step

        # Reset retry counter on successful action generation
        invalid_action_retries = 0

        # Step 3: Execute action
        try:
            observation, stop_result = await _execute_action(
                action, state, emit, registry
            )
        except Exception as exc:
            logger.warning(
                "react_action_execution_failed",
                step=step,
                action_type=action.type,
                error=str(exc),
                run_id=str(state.run_id),
            )
            observation = f"Action failed: {str(exc)}"
            stop_result = None

        # Step 4: Emit events
        await emit(AgentThoughtEvent(step=step, thought=thought))
        await emit(
            AgentActionEvent(
                step=step,
                action_type=action.type,
                args=action.model_dump(exclude={"type"}),
            )
        )
        await emit(
            AgentObservationEvent(
                step=step,
                result_summary=observation[:500],  # Truncate for brevity
                tokens=len(observation.split()),
            )
        )

        # Step 5: Add to history
        react_step = ReactStep(
            step=step,
            thought=thought,
            action=action,
            observation=observation,
        )
        state.react_history.append(react_step)
        state.react_step_count = step + 1

        # Step 6: Check for FinishAction or stop result
        if stop_result:
            logger.info(
                "react_loop_stopped_by_action",
                step=step,
                stop_reason=stop_result,
                run_id=str(state.run_id),
            )
            # Summarize if needed before returning
            await _maybe_summarize_history(state, emit)
            return stop_result

        # Step 6b: BRD-26 §4.13 cost-gated meta-judge hook
        # (after_react_observation). Counter already advanced in Step 5,
        # so the gate sees the up-to-date `react_step_count`.
        if _cost_gate_after_react_ok(state):
            meta_outcome = await maybe_run_meta_judge(
                state,
                emit,
                _synthetic_signal_from_react(state),
                hook="after_react_observation",
            )
            if meta_outcome == "stop_best_effort":
                # PR-6b: positive terminal via AnswerKind=BEST_EFFORT
                # inside JUDGE_CONFIRMED (WP-3 stop_reason collapse).
                logger.info(
                    "react_loop_stopped_by_meta_judge",
                    step=step,
                    outcome=meta_outcome,
                    run_id=str(state.run_id),
                )
                await _maybe_summarize_history(state, emit)
                return StopReason.JUDGE_CONFIRMED
            if meta_outcome == "confirm":
                logger.info(
                    "react_loop_stopped_by_meta_judge",
                    step=step,
                    outcome=meta_outcome,
                    run_id=str(state.run_id),
                )
                await _maybe_summarize_history(state, emit)
                return StopReason.JUDGE_CONFIRMED
            # "continue" / "skipped" — fall through to intra-loop signals.

        # Step 7: Check intra-loop stopping signals
        from app.stopping.react_intra_loop import evaluate_react_intra_loop

        stop_decision = await evaluate_react_intra_loop(state)
        if stop_decision and stop_decision.result == "stop":
            logger.info(
                "react_loop_stopped_by_signal",
                step=step,
                signal=stop_decision.signal_name,
                stop_reason=stop_decision.stop_reason,
                run_id=str(state.run_id),
            )
            await _maybe_summarize_history(state, emit)
            return stop_decision.stop_reason  # type: ignore

        step += 1

    # Step cap reached
    logger.info(
        "react_loop_step_cap_reached",
        max_steps=max_steps,
        run_id=str(state.run_id),
    )
    await _maybe_summarize_history(state, emit)
    return "forced_synth"


async def _generate_thought(state: RunState) -> str:
    """Generate reasoning thought using PLANNER role."""
    from app.agent.react.prompts import REACT_THOUGHT_PROMPT

    hypotheses_text = "\n".join(
        f"{i + 1}. [{h.verdict.upper()}] {h.text} (priority: {h.priority:.2f})"
        for i, h in enumerate(state.hypotheses)
    )

    history_text = "\n".join(
        f"Step {s.step}: {s.thought} → {s.action.type} → {s.observation[:100]}..."
        for s in state.react_history[-4:]  # Last 4 steps for context
    )

    response = await llm.call(
        role=LLMRole.PLANNER,
        messages=[
            {
                "role": "system",
                "content": REACT_THOUGHT_PROMPT.format(
                    question=state.question,
                    hypotheses=hypotheses_text or "No hypotheses yet",
                    history=history_text or "No history yet",
                ),
            },
            {"role": "user", "content": "What should I investigate next?"},
        ],
        response_model=ThoughtOutput,
    )

    return response.thought


async def _generate_action(state: RunState, thought: str) -> AgentActionUnion:
    """Generate action using PLANNER role with discriminated union."""
    from app.agent.react.prompts import REACT_ACTION_PROMPT

    hypotheses_text = "\n".join(
        f"{i + 1}. [{h.verdict.upper()}] {h.text}"
        for i, h in enumerate(state.hypotheses)
    )

    response = await llm.call(
        role=LLMRole.PLANNER,
        messages=[
            {
                "role": "system",
                "content": REACT_ACTION_PROMPT.format(
                    question=state.question,
                    hypotheses=hypotheses_text,
                    thought=thought,
                ),
            },
            {"role": "user", "content": "Choose an action."},
        ],
        response_model=AgentActionUnion,
    )

    return response


async def _execute_action(
    action: AgentActionUnion,
    state: RunState,
    emit: Callable[[BaseEvent], Awaitable[None]],
    registry: SourceRegistry,
) -> tuple[str, StopReason | Literal["forced_synth"] | None]:
    """Execute action and return (observation, optional_stop_reason)."""
    match action:
        case SearchAction():
            return await _execute_search(action, state, emit, registry)
        case DeepFetchAction():
            return await _execute_deep_fetch(action, state, emit, registry)
        case EvaluateHypothesisAction():
            return await _execute_evaluate_hypothesis(action, state, emit)
        case FinishAction():
            return await _execute_finish(action, state)
        case _:
            return f"Unknown action type: {type(action)}", None


async def _execute_search(
    action: SearchAction,
    state: RunState,
    emit: Callable[[BaseEvent], Awaitable[None]],
    registry: SourceRegistry,
) -> tuple[str, None]:
    """Execute search action via Source seam."""
    source_type = action.source_hint or registry.types()[0]
    source = registry.get(source_type)

    # Emit ToolCalledEvent
    await emit(
        ToolCalledEvent(
            source_type=source_type,
            query=action.query,
            query_intent=f"ReAct search: {action.query[:80]}",
            target_claim_id=None,
            query_length_tokens=len(action.query.split()),
            tavily_days_filter=state.tavily_days_filter,
        )
    )

    try:
        results: list[SourceResult] = await source.search(
            action.query, max_results=_MAX_RESULTS_PER_SEARCH
        )

        # Add top results as evidence
        evidence_summaries: list[str] = []
        for result in results[:3]:  # Top 3
            result_text = result.content or result.snippet
            evidence_item = EvidenceItem(
                event_id=uuid4(),
                claim_id="react_search",
                source_url=result.url,
                source_title=result.title,
                text=result_text[:500],
                polarity=EvidencePolarity.SUPPORTS.value,
                confidence=0.7,
            )
            state.add_evidence(evidence_item)

            await emit(
                EvidenceAddedEvent(
                    source_type=source_type,
                    target_claim_id="react_search",
                    source_url=result.url,
                    source_title=result.title,
                    extracted_text=result_text[:500],
                    polarity=EvidencePolarity.SUPPORTS,
                    confidence=0.7,
                )
            )

            evidence_summaries.append(
                f"- {result.title}: {result_text[:200]}..."
            )

        observation = (
            f"Found {len(results)} results:\n" + "\n".join(evidence_summaries)
            if evidence_summaries
            else "No results found"
        )

    except Exception as exc:
        observation = f"Search failed: {str(exc)}"
        logger.warning(
            "react_search_failed",
            query=action.query,
            error=str(exc),
            run_id=str(state.run_id),
        )

    return observation, None


async def _execute_deep_fetch(
    action: DeepFetchAction,
    state: RunState,
    emit: Callable[[BaseEvent], Awaitable[None]],
    registry: SourceRegistry,
) -> tuple[str, None]:
    """Execute deep fetch action via Source seam."""
    # Use first available source for fetch_full (typically Tavily)
    source_type = registry.types()[0]
    source = registry.get(source_type)

    try:
        fetched = await source.fetch_full(action.url)
        if fetched is None:
            observation = f"Deep fetch returned no content for {action.url}"
            return observation, None
        content = fetched.content or fetched.snippet
        title = fetched.title or action.url.split("/")[-1][:50]

        # Add as evidence
        evidence_item = EvidenceItem(
            event_id=uuid4(),
            claim_id="react_deep_fetch",
            source_url=action.url,
            source_title=title,
            text=content[:1000],
            polarity=EvidencePolarity.SUPPORTS.value,
            confidence=0.8,
        )
        state.add_evidence(evidence_item)

        await emit(
            EvidenceAddedEvent(
                source_type=source_type,
                target_claim_id="react_deep_fetch",
                source_url=action.url,
                source_title=title,
                extracted_text=content[:1000],
                polarity=EvidencePolarity.SUPPORTS,
                confidence=0.8,
            )
        )

        observation = f"Fetched {len(content)} chars from {action.url}"

    except Exception as exc:
        observation = f"Deep fetch failed: {str(exc)}"
        logger.warning(
            "react_deep_fetch_failed",
            url=action.url,
            error=str(exc),
            run_id=str(state.run_id),
        )

    return observation, None


async def _execute_evaluate_hypothesis(
    action: EvaluateHypothesisAction,
    state: RunState,
    emit: Callable[[BaseEvent], Awaitable[None]],
) -> tuple[str, None]:
    """Execute hypothesis evaluation action."""
    # Find hypothesis by ID
    hypothesis = None
    for h in state.hypotheses:
        if h.id == action.hypothesis_id:
            hypothesis = h
            break

    if not hypothesis:
        return f"Hypothesis {action.hypothesis_id} not found", None

    # Update verdict
    old_verdict = hypothesis.verdict
    hypothesis.verdict = action.verdict

    # Attach recent evidence IDs (last 3 evidence items)
    recent_evidence_ids = [e.event_id for e in state.evidence[-3:]]
    hypothesis.evidence_ids.extend(recent_evidence_ids)

    # Emit event
    await emit(
        HypothesisEvaluatedEvent(
            hypothesis_id=action.hypothesis_id,
            verdict=action.verdict,
            evidence_ids=recent_evidence_ids,
        )
    )

    observation = (
        f"Hypothesis '{hypothesis.text[:50]}...' evaluated: "
        f"{old_verdict} → {action.verdict}"
    )

    return observation, None


async def _execute_finish(
    action: FinishAction,
    state: RunState,
) -> tuple[str, StopReason | Literal["forced_synth"]]:
    """Execute finish action."""
    observation = f"Finishing: {action.reason}"

    # Decide stop reason based on what the agent gathered.
    # Two acceptance paths:
    #   1) Explicit hypothesis evaluation: at least one confirmed AND
    #      structural confidence already meets threshold (FAST-style runs
    #      where last_structural_confidence is populated).
    #   2) Evidence-grounded finish: the DEEP lane does NOT update
    #      last_structural_confidence, so a confirmed-hypothesis run with
    #      sufficient gathered evidence is also accepted. This prevents the
    #      loop from silently downgrading a voluntary finish to forced_synth
    #      whenever the agent reasoned in prose without emitting an
    #      EvaluateHypothesisAction (a frequent failure mode that surfaced
    #      to users as a misleading "Reached search limit (0 rounds)" stop).
    confirmed_count = sum(1 for h in state.hypotheses if h.verdict == "confirmed")
    structural_ok = (state.last_structural_confidence or 0.0) >= 0.75
    has_substantial_evidence = len(state.evidence) >= 3

    if confirmed_count > 0 and structural_ok:
        return observation, StopReason.JUDGE_CONFIRMED
    if has_substantial_evidence:
        # Trust the agent's voluntary finish when grounded in evidence.
        # Returning JUDGE_CONFIRMED routes to the direct-synthesis path in
        # the DEEP lane (skipping the secondary CoVe + mini-judge gate).
        return observation, StopReason.JUDGE_CONFIRMED
    # Otherwise force synthesis with whatever evidence exists.
    return observation, "forced_synth"


async def _maybe_summarize_history(
    state: RunState,
    emit: Callable[[BaseEvent], Awaitable[None]],
) -> None:
    """Summarize history if it exceeds token budget."""
    if not state.react_history:
        return

    summarized_history, steps_summarized = await summarize_history_if_needed(
        state.react_history,
        max_tokens=state.max_react_steps * 2000,  # Approx budget
    )

    if steps_summarized:
        state.react_history = summarized_history
        summary_tokens = len(summarized_history[0].thought.split()) if summarized_history else 0

        await emit(
            HistorySummarizedEvent(
                steps_summarized=steps_summarized,
                summary_tokens=summary_tokens,
            )
        )

        logger.info(
            "react_history_summarized",
            steps_summarized=steps_summarized,
            new_length=len(summarized_history),
            run_id=str(state.run_id),
        )

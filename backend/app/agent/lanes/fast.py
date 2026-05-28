"""FAST lane execution (IP-25 Phase C).

Single-round search (Wikipedia + Tavily top-3 each) + short synthesis +
mini-judge. Escalates to STANDARD on low confidence or judge rejection.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal
from uuid import uuid4

import structlog

from app.agent.run_state import EvidenceItem, RunState
from app.domain.enums import EvidencePolarity, SourceType, StopReason
from app.domain.events import BaseEvent, EvidenceAddedEvent, ToolCalledEvent
from app.llm import LLMRole, llm
from app.llm.models import MiniJudgeVerdict, SynthesizedAnswer
from app.llm.prompts import FAST_MINI_JUDGE_PROMPT, FAST_SYNTH_PROMPT
from app.seams.source import SourceResult
from app.sources.registry import get_registry

logger = structlog.get_logger(__name__)

_FAST_RESULTS_PER_SOURCE = 3
_FAST_S_THRESHOLD = 0.85


async def execute_fast_lane(
    state: RunState,
    emit: Callable[[BaseEvent], Awaitable[None]],
) -> StopReason | Literal["escalate"]:
    """Execute FAST lane pipeline: search → synth → mini-judge.

    Args:
        state: RunState instance with question already normalized and classified
        emit: Async callable for emitting events

    Returns:
        StopReason.JUDGE_CONFIRMED if fast path succeeds, "escalate" otherwise

    Logic:
        1. Emit ToolCalled for Wikipedia + Tavily (parallel, top-3 each)
        2. Call synthesizer with FAST_SYNTH_PROMPT → 1-2 sentence answer
        3. Call mini-judge with FAST_MINI_JUDGE_PROMPT → MiniJudgeVerdict
        4. If S_effective >= 0.85 AND mini_judge.ok → JUDGE_CONFIRMED
        5. Else → "escalate" to STANDARD lane

    Mutations:
        - Adds evidence to state.evidence (for finalization compatibility)
        - Sets state.draft_answer and state.final_answer on success
        - Sets state.last_judge_confidence and state.judge_verdict on success
    """
    registry = get_registry()
    query = state.question

    # Step 1: Parallel search (Wikipedia + Tavily)
    search_tasks: list[Awaitable[list[SourceResult]]] = []
    tool_events: list[ToolCalledEvent] = []
    source_types_list: list[SourceType] = []

    for source_type in [SourceType.WIKIPEDIA, SourceType.TAVILY]:
        if source_type not in registry.types():
            continue

        tool_event = ToolCalledEvent(
            source_type=source_type,
            query=query,
            query_intent=f"FAST lane search: {query[:80]}",
            target_claim_id=None,
            query_length_tokens=len(query.split()),
            tavily_days_filter=None,
        )
        tool_events.append(tool_event)
        source_types_list.append(source_type)

        source = registry.get(source_type)
        search_tasks.append(source.search(query, max_results=_FAST_RESULTS_PER_SOURCE))

    # Emit tool events
    for tool_event in tool_events:
        await emit(tool_event)

    # Execute searches in parallel
    try:
        results_list: list[list[SourceResult] | BaseException] = await asyncio.gather(
            *search_tasks, return_exceptions=True
        )
    except Exception as exc:
        logger.warning(
            "fast_lane_search_failed",
            error=str(exc),
            run_id=str(state.run_id),
        )
        return "escalate"

    # Collect evidence (deterministic order: Wikipedia first, then Tavily)
    evidence_items: list[EvidenceItem] = []
    for source_type, results in zip(source_types_list, results_list, strict=True):
        if isinstance(results, BaseException):
            logger.warning(
                "fast_lane_source_exception",
                error=str(results),
                run_id=str(state.run_id),
            )
            continue

        for result in results:
            evidence_item = EvidenceItem(
                event_id=uuid4(),
                claim_id="fast_lane_single_claim",
                source_url=result.url,
                source_title=result.title,
                text=result.snippet,
                polarity=EvidencePolarity.NEUTRAL.value,
                confidence=result.relevance_score or 0.5,
                source_published_date=None,
                authority_tier=None,
            )
            evidence_items.append(evidence_item)
            state.add_evidence(evidence_item)

            # Emit EvidenceAdded
            await emit(
                EvidenceAddedEvent(
                    target_claim_id="fast_lane_single_claim",
                    source_url=result.url,
                    source_title=result.title,
                    extracted_text=result.snippet,
                    polarity=EvidencePolarity.NEUTRAL,
                    source_type=source_type,
                    confidence=result.relevance_score or 0.5,
                )
            )

    # Step 2: Calculate structural confidence
    # For FAST lane with no sub-claims, use a simplified proxy:
    # min(1.0, num_evidence_items / 6) as a basic coverage metric
    num_evidence = len(evidence_items)
    S_effective = min(1.0, num_evidence / 6.0)

    # Check early escalation: insufficient evidence
    if S_effective < _FAST_S_THRESHOLD:
        logger.info(
            "fast_lane_escalate_low_s",
            s_effective=S_effective,
            num_evidence=num_evidence,
            run_id=str(state.run_id),
        )
        return "escalate"

    # Step 3: Synthesize answer
    evidence_list = [
        {
            "url": e.source_url,
            "title": e.source_title,
            "snippet": e.text,
        }
        for e in evidence_items
    ]

    try:
        synth_result = await llm.call(
            role=LLMRole.SYNTHESIZER,
            messages=[
                {"role": "system", "content": FAST_SYNTH_PROMPT},
                {"role": "user", "content": f"Question: {state.question}\n\nEvidence:\n" + "\n".join(
                    f"- [{e['title']}]({e['url']}): {e['snippet'][:150]}"
                    for e in evidence_list
                )},
            ],
            response_model=SynthesizedAnswer,
            max_tokens=500,
        )
    except Exception as exc:
        logger.warning(
            "fast_lane_synth_failed",
            error=str(exc),
            run_id=str(state.run_id),
        )
        return "escalate"

    # Step 4: Mini-judge evaluation
    try:
        mini_judge_result = await llm.call(
            role=LLMRole.JUDGE,
            messages=[
                {"role": "system", "content": FAST_MINI_JUDGE_PROMPT},
                {"role": "user", "content": (
                    f"Question: {state.question}\n\n"
                    f"Answer: {synth_result.prose}\n\n"
                    f"Sources ({len(evidence_list)}):\n" +
                    "\n".join(f"- [{e['title']}]({e['url']})" for e in evidence_list)
                )},
            ],
            response_model=MiniJudgeVerdict,
            max_tokens=300,
        )
    except Exception as exc:
        logger.warning(
            "fast_lane_judge_failed",
            error=str(exc),
            run_id=str(state.run_id),
        )
        return "escalate"

    # Step 5: Decision
    if mini_judge_result.ok and S_effective >= _FAST_S_THRESHOLD:
        # Success — finalize and return JUDGE_CONFIRMED
        state.draft_answer = synth_result.prose
        state.draft_payload = synth_result
        state.final_answer = synth_result.prose
        state.last_judge_confidence = mini_judge_result.j_score
        state.last_structural_confidence = S_effective

        # PR-3 Mejora 3.2: emit DraftSynthesized for audit trail (RF-03).
        from app.domain.events import DraftSynthesizedEvent

        await emit(
            DraftSynthesizedEvent(
                prose=synth_result.prose,
                answer_kind=synth_result.answer_kind,
                citation_count=len(synth_result.citations),
                key_point_count=len(synth_result.key_points),
                source="fast",
            )
        )

        logger.info(
            "fast_lane_success",
            j_score=mini_judge_result.j_score,
            s_effective=S_effective,
            run_id=str(state.run_id),
        )
        return StopReason.JUDGE_CONFIRMED

    # Escalate to STANDARD
    logger.info(
        "fast_lane_escalate_judge_rejected",
        mini_judge_ok=mini_judge_result.ok,
        j_score=mini_judge_result.j_score,
        reason=mini_judge_result.reason,
        run_id=str(state.run_id),
    )
    return "escalate"

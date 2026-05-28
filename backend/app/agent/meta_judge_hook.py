"""Reflective meta-judge hook (BRD-26 §4.6) shared across lanes.

Single entry point so the orchestrator (STANDARD ``after_judge``) and the
DEEP lane (``after_cove``) drive the meta-judge through the same
decision tree. Always fail-safe: any LLM error returns ``"skipped"`` and
is logged but never blocks the run.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal
from uuid import UUID, uuid4

import structlog

from app.agent.run_state import RunState
from app.config import settings
from app.domain.enums import Lane
from app.domain.events import (
    AdversarialObjectionsGeneratedEvent,
    BaseEvent,
    DirectedSubclaimsFromObjectionsEvent,
    MetaStopVerdictEvent,
    SubClaim,
)
from app.llm.client import llm
from app.llm.meta_judge import (
    MetaJudgeContext,
    evaluate_value_of_continuation,
    generate_adversarial_objections,
)

logger = structlog.get_logger(__name__)

MetaJudgeOutcome = Literal["stop_best_effort", "confirm", "continue", "skipped"]
MetaJudgeHook = Literal["after_judge", "after_cove", "after_react_observation"]


async def maybe_run_meta_judge(
    state: RunState,
    emit: Callable[[BaseEvent], Awaitable[None]],
    judge_signal: Any,
    *,
    hook: MetaJudgeHook = "after_judge",
) -> MetaJudgeOutcome:
    """Run VoC + Adversarial Completeness (BRD-26 §4.6).

    ``judge_signal`` is duck-typed: it must expose ``passed``,
    ``judge_confidence``, ``structural_confidence``, ``final_confidence``
    and ``rationale``. For the DEEP ``after_cove`` hook a synthetic
    placeholder built from RunState is acceptable (no judge ruling
    exists yet at that point).
    """
    if not settings.meta_judge_enabled:
        return "skipped"
    if state.selected_lane == Lane.FAST:
        return "skipped"
    if getattr(judge_signal, "passed", False):
        return "skipped"
    if state.judge_attempts >= state.max_judge_attempts:
        return "skipped"

    rounds_remaining = max(0, state.max_searches - state.search_count)
    authority_mix: dict[str, int] = {}
    for item in state.evidence:
        tier = getattr(item, "authority_tier", None)
        key = str(tier.value) if hasattr(tier, "value") else str(tier or "unknown")
        authority_mix[key] = authority_mix.get(key, 0) + 1

    ctx = MetaJudgeContext(
        question=state.question,
        answer_kind=(
            state.selected_answer_kind.value
            if state.selected_answer_kind is not None
            else None
        ),
        lane=(state.selected_lane.value if state.selected_lane is not None else "standard"),
        subclaim_count=len(state.sub_claims),
        evidence_count=len(state.evidence),
        authority_mix=authority_mix,
        structural_confidence=judge_signal.structural_confidence,
        judge_confidence=judge_signal.judge_confidence,
        threshold=state.confidence_threshold,
        rounds_used=state.search_count,
        rounds_remaining=rounds_remaining,
        last_judge_rationale=judge_signal.rationale,
        draft_prose=state.draft_answer,
    )

    lane = state.selected_lane or Lane.STANDARD

    try:
        voc = await evaluate_value_of_continuation(llm, ctx)
    except Exception:  # pragma: no cover — meta-judge never blocks the run
        logger.exception("meta_judge_voc_failed", run_id=str(state.run_id), hook=hook)
        return "skipped"

    await emit(
        MetaStopVerdictEvent(
            lane=lane,
            hook=hook,
            verdict=voc,
            confidence_at_check=judge_signal.final_confidence,
            rounds_used=state.search_count,
            rounds_remaining=rounds_remaining,
        )
    )

    if voc.decision == "stop_best_effort":
        return "stop_best_effort"

    if voc.decision == "stop":
        return "continue"  # caller's regular flow chooses the StopReason

    if voc.expected_delta_s < settings.meta_judge_min_delta_s:
        return "continue"

    try:
        ac = await generate_adversarial_objections(llm, ctx)
    except Exception:  # pragma: no cover — never block the run
        logger.exception("meta_judge_ac_failed", run_id=str(state.run_id), hook=hook)
        return "continue"

    await emit(AdversarialObjectionsGeneratedEvent(lane=lane, verdict=ac))

    if ac.all_answered:
        return "confirm"

    actionable = [
        obj for obj in ac.objections if obj.status == "unanswered_needs_search"
    ]
    if actionable:
        objection_texts: list[str] = []
        new_ids: list[UUID] = []
        for obj in actionable:
            new_uuid = uuid4()
            claim_text = (obj.suggested_query or obj.text).strip()
            if not claim_text:
                continue
            state.sub_claims.append(
                SubClaim(id=str(new_uuid), text=claim_text, status="pending")
            )
            objection_texts.append(obj.text)
            new_ids.append(new_uuid)
        if new_ids:
            await emit(
                DirectedSubclaimsFromObjectionsEvent(
                    lane=lane,
                    objection_texts=objection_texts,
                    new_subclaim_ids=new_ids,
                )
            )
    return "continue"

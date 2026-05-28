"""Unit tests for ``app.llm.meta_judge`` helpers (BRD-26)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.domain.meta_stop import (
    AdversarialCompletenessVerdict,
    Objection,
    ValueOfContinuationVerdict,
)
from app.llm.meta_judge import (
    MetaJudgeContext,
    evaluate_value_of_continuation,
    generate_adversarial_objections,
)
from app.llm.roles import LLMRole


def _ctx(**overrides: Any) -> MetaJudgeContext:
    base = dict(
        question="When did Japan adopt the Meiji constitution?",
        answer_kind="direct",
        lane="standard",
        subclaim_count=3,
        evidence_count=4,
        authority_mix={"tier_1": 1, "tier_2": 2},
        structural_confidence=0.61,
        judge_confidence=0.58,
        threshold=0.7,
        rounds_used=2,
        rounds_remaining=2,
        last_judge_rationale="Needs primary source",
        draft_prose="Draft body.",
    )
    base.update(overrides)
    return MetaJudgeContext(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_voc_helper_calls_meta_judge_role() -> None:
    expected = ValueOfContinuationVerdict(
        decision="continue",
        expected_delta_s=0.08,
        next_action_hypothesis="search primary constitution text",
        reason="missing primary source",
    )
    client = AsyncMock()
    client.call.return_value = expected

    result = await evaluate_value_of_continuation(client, _ctx())

    assert result is expected
    call = client.call.await_args
    assert call is not None
    assert call.kwargs["role"] == LLMRole.META_JUDGE
    assert call.kwargs["response_model"] is ValueOfContinuationVerdict
    messages = call.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "Value of Continuation" in messages[0]["content"] or "research round" in messages[0]["content"]
    assert "Meiji" in messages[-1]["content"]


@pytest.mark.asyncio
async def test_adversarial_helper_calls_meta_judge_role() -> None:
    objections = [
        Objection(text="stale", status="unanswered_needs_search", evidence_ids_answering=[], suggested_query="2025 update"),
        Objection(text="ambig", status="answered_by_evidence", evidence_ids_answering=[]),
        Objection(text="echo", status="unanswered_no_search_possible", evidence_ids_answering=[]),
    ]
    expected = AdversarialCompletenessVerdict(objections=objections)
    client = AsyncMock()
    client.call.return_value = expected

    result = await generate_adversarial_objections(client, _ctx())

    assert result is expected
    call = client.call.await_args
    assert call is not None
    assert call.kwargs["role"] == LLMRole.META_JUDGE
    assert call.kwargs["response_model"] is AdversarialCompletenessVerdict
    messages = call.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "objection" in messages[0]["content"].lower()


def test_meta_judge_role_registered() -> None:
    """Smoke check: META_JUDGE has a model pool and a system prompt."""
    from app.llm.prompts import ROLE_PROMPTS
    from app.llm.roles import ROLE_CONFIGS

    assert LLMRole.META_JUDGE in ROLE_CONFIGS
    assert LLMRole.META_JUDGE in ROLE_PROMPTS
    assert ROLE_CONFIGS[LLMRole.META_JUDGE].models, "META_JUDGE must have at least one model"

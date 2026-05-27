"""Tests for ``app.llm.client.LLMClient``."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.llm import client as client_module
from app.llm.models import (
    JudgeVerdict,
    PlanOutput,
    QuestionClassification,
    SubClaimOutput,
    SynthesizedAnswer,
)
from app.llm.prompts import ROLE_PROMPTS
from app.llm.roles import ROLE_CONFIGS, LLMRole


@pytest.fixture
def mock_create(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Replace ``client.chat.completions.create`` with an AsyncMock."""
    mock = AsyncMock()
    monkeypatch.setattr(
        client_module.client.chat.completions, "create", mock
    )
    return mock


@pytest.mark.asyncio
async def test_call_classifier_returns_question_classification(
    mock_create: AsyncMock,
) -> None:
    expected = QuestionClassification(
        question_type=1, rationale="factual", answerable=True
    )
    mock_create.return_value = expected

    result = await client_module.llm.call(
        LLMRole.CLASSIFIER,
        [{"role": "user", "content": "What is the capital of France?"}],
        QuestionClassification,
    )

    assert result is expected
    kwargs = mock_create.call_args.kwargs
    assert kwargs["model"] == ROLE_CONFIGS[LLMRole.CLASSIFIER].model
    assert kwargs["temperature"] == ROLE_CONFIGS[LLMRole.CLASSIFIER].temperature
    assert kwargs["max_tokens"] == ROLE_CONFIGS[LLMRole.CLASSIFIER].max_tokens
    assert kwargs["response_model"] is QuestionClassification


@pytest.mark.asyncio
async def test_call_planner_returns_plan_output(mock_create: AsyncMock) -> None:
    expected = PlanOutput(
        sub_claims=[SubClaimOutput(id="c1", text="t", rationale="r")],
        overall_rationale="ok",
    )
    mock_create.return_value = expected

    result = await client_module.llm.call(
        LLMRole.PLANNER,
        [{"role": "user", "content": "Plan this."}],
        PlanOutput,
    )

    assert result is expected
    assert mock_create.call_args.kwargs["model"] == ROLE_CONFIGS[LLMRole.PLANNER].model


@pytest.mark.asyncio
async def test_call_synthesizer_returns_synthesized_answer(
    mock_create: AsyncMock,
) -> None:
    expected = SynthesizedAnswer(prose="answer", key_points=["a"])
    mock_create.return_value = expected

    result = await client_module.llm.call(
        LLMRole.SYNTHESIZER,
        [{"role": "user", "content": "Synthesize"}],
        SynthesizedAnswer,
    )

    assert result is expected
    assert (
        mock_create.call_args.kwargs["model"]
        == ROLE_CONFIGS[LLMRole.SYNTHESIZER].model
    )


@pytest.mark.asyncio
async def test_call_judge_returns_verdict(mock_create: AsyncMock) -> None:
    expected = JudgeVerdict(confidence=0.8, verdict="approve", rationale="ok")
    mock_create.return_value = expected

    result = await client_module.llm.call(
        LLMRole.JUDGE,
        [{"role": "user", "content": "Judge this"}],
        JudgeVerdict,
    )

    assert result is expected
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio
async def test_call_prepends_role_system_prompt_when_absent(
    mock_create: AsyncMock,
) -> None:
    mock_create.return_value = SynthesizedAnswer(prose="x", key_points=[])

    await client_module.llm.call(
        LLMRole.SYNTHESIZER,
        [{"role": "user", "content": "Hi"}],
        SynthesizedAnswer,
    )

    messages: list[dict[str, str]] = mock_create.call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == ROLE_PROMPTS[LLMRole.SYNTHESIZER]
    assert messages[1] == {"role": "user", "content": "Hi"}


@pytest.mark.asyncio
async def test_call_does_not_prepend_system_when_present(
    mock_create: AsyncMock,
) -> None:
    mock_create.return_value = SynthesizedAnswer(prose="x", key_points=[])
    custom: list[dict[str, str]] = [
        {"role": "system", "content": "Custom system prompt"},
        {"role": "user", "content": "Hi"},
    ]

    await client_module.llm.call(LLMRole.SYNTHESIZER, custom, SynthesizedAnswer)

    messages: list[dict[str, str]] = mock_create.call_args.kwargs["messages"]
    system_messages = [m for m in messages if m["role"] == "system"]
    assert len(system_messages) == 1
    assert system_messages[0]["content"] == "Custom system prompt"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "response_model", "instance"),
    [
        (
            LLMRole.CLASSIFIER,
            QuestionClassification,
            QuestionClassification(question_type="factual", rationale="r", answerable=True),
        ),
        (
            LLMRole.PLANNER,
            PlanOutput,
            PlanOutput(
                sub_claims=[SubClaimOutput(id="c1", text="t", rationale="r")],
                overall_rationale="r",
            ),
        ),
        (
            LLMRole.SYNTHESIZER,
            SynthesizedAnswer,
            SynthesizedAnswer(prose="p", key_points=["k"]),
        ),
        (
            LLMRole.JUDGE,
            JudgeVerdict,
            JudgeVerdict(confidence=0.5, verdict="approve", rationale="r"),
        ),
    ],
)
async def test_call_success_path_for_each_role(
    mock_create: AsyncMock,
    role: LLMRole,
    response_model: type[Any],
    instance: Any,
) -> None:
    mock_create.return_value = instance

    result = await client_module.llm.call(
        role, [{"role": "user", "content": "go"}], response_model
    )

    assert result is instance
    assert mock_create.call_args.kwargs["model"] == ROLE_CONFIGS[role].model
    assert mock_create.call_args.kwargs["response_model"] is response_model

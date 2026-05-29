"""Tests for the LLM cost-emission instrumentation in ``app.llm.client``.

Asserts that one CostIncurredEvent is appended for each successful LLM call
when ``current_emitter`` is set, and that failure paths emit nothing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.domain.enums import EventType
from app.domain.events import BaseEvent, CostIncurredEvent
from app.llm import client as client_module
from app.llm import pricing as pricing_module
from app.llm.client import current_provider
from app.llm.context import current_emitter
from app.llm.models import QuestionClassification
from app.llm.roles import LLMRole


@pytest.fixture
def captured() -> list[BaseEvent]:
    return []


@pytest.fixture
def emitter(captured: list[BaseEvent]) -> Callable[[BaseEvent], Awaitable[None]]:
    async def _emit(ev: BaseEvent) -> None:
        captured.append(ev)

    return _emit


@pytest.fixture(autouse=True)
def _reset_provider() -> Any:
    # Force the GitHub branch by default so the monkeypatched create() fires.
    token = current_provider.set("github")
    yield
    current_provider.reset(token)


@pytest.fixture
def mock_create(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(client_module.client.chat.completions, "create", mock)
    return mock


def _classification_with_usage(prompt: int, completion: int) -> QuestionClassification:
    obj = QuestionClassification(
        question_type="factual", rationale="ok", answerable=True
    )
    raw = SimpleNamespace(usage=SimpleNamespace(
        prompt_tokens=prompt, completion_tokens=completion
    ))
    # instructor attaches the raw httpx-style response here.
    obj._raw_response = raw  # type: ignore[attr-defined]
    return obj


@pytest.mark.asyncio
async def test_successful_call_emits_one_cost_event(
    mock_create: AsyncMock,
    captured: list[BaseEvent],
    emitter: Callable[[BaseEvent], Awaitable[None]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_create.return_value = _classification_with_usage(800, 100)
    monkeypatch.setattr(
        pricing_module.litellm,
        "completion_cost",
        lambda completion_response: 0.0021,
    )
    token = current_emitter.set(emitter)
    try:
        await client_module.llm.call(
            LLMRole.CLASSIFIER,
            [{"role": "user", "content": "x"}],
            QuestionClassification,
        )
    finally:
        current_emitter.reset(token)

    cost_events = [e for e in captured if isinstance(e, CostIncurredEvent)]
    assert len(cost_events) == 1
    ev = cost_events[0]
    assert ev.type == EventType.COST_INCURRED
    assert ev.provider == "github"
    assert ev.kind == "llm"
    assert ev.prompt_tokens == 800
    assert ev.completion_tokens == 100
    assert ev.cost_usd == pytest.approx(0.0021)
    assert ev.pricing_source == "litellm"
    assert ev.latency_ms >= 0


@pytest.mark.asyncio
async def test_no_emitter_set_does_not_raise(
    mock_create: AsyncMock,
    captured: list[BaseEvent],
) -> None:
    mock_create.return_value = _classification_with_usage(100, 50)
    # No current_emitter.set() — emitter is None.
    result = await client_module.llm.call(
        LLMRole.CLASSIFIER,
        [{"role": "user", "content": "x"}],
        QuestionClassification,
    )
    assert isinstance(result, QuestionClassification)
    assert captured == []


@pytest.mark.asyncio
async def test_failed_call_emits_nothing(
    mock_create: AsyncMock,
    captured: list[BaseEvent],
    emitter: Callable[[BaseEvent], Awaitable[None]],
) -> None:
    mock_create.side_effect = RuntimeError("boom")
    token = current_emitter.set(emitter)
    try:
        with pytest.raises(RuntimeError):
            await client_module.llm.call(
                LLMRole.CLASSIFIER,
                [{"role": "user", "content": "x"}],
                QuestionClassification,
            )
    finally:
        current_emitter.reset(token)

    assert [e for e in captured if isinstance(e, CostIncurredEvent)] == []


@pytest.mark.asyncio
async def test_emitter_failure_does_not_break_call(
    mock_create: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_create.return_value = _classification_with_usage(10, 5)
    monkeypatch.setattr(
        pricing_module.litellm,
        "completion_cost",
        lambda completion_response: 0.001,
    )

    async def _boom(_ev: BaseEvent) -> None:
        raise RuntimeError("emitter exploded")

    token = current_emitter.set(_boom)
    try:
        # Must NOT raise — _emit_llm_cost swallows all exceptions.
        result = await client_module.llm.call(
            LLMRole.CLASSIFIER,
            [{"role": "user", "content": "x"}],
            QuestionClassification,
        )
    finally:
        current_emitter.reset(token)

    assert isinstance(result, QuestionClassification)

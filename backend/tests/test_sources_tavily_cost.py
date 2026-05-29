"""Tests for cost emission in ``TavilySource``."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from app.domain.events import BaseEvent, CostIncurredEvent
from app.llm.context import current_emitter
from app.sources.tavily import TavilySource


@pytest.fixture
def captured() -> list[BaseEvent]:
    return []


@pytest.fixture
def emitter(captured: list[BaseEvent]) -> Callable[[BaseEvent], Awaitable[None]]:
    async def _emit(ev: BaseEvent) -> None:
        captured.append(ev)

    return _emit


@pytest.fixture(autouse=True)
def _bind_emitter(emitter: Callable[[BaseEvent], Awaitable[None]]) -> Any:
    token = current_emitter.set(emitter)
    yield
    current_emitter.reset(token)


@pytest.mark.asyncio
async def test_search_emits_one_cost_event(
    monkeypatch: pytest.MonkeyPatch, captured: list[BaseEvent]
) -> None:
    src = TavilySource(api_key="test")

    async def _stub_search(**_: Any) -> dict[str, Any]:
        return {"results": [
            {"url": "https://x", "title": "t", "content": "c", "raw_content": "r"}
        ]}

    monkeypatch.setattr(src._client, "search", _stub_search)

    await src.search("hello", max_results=3)

    costs = [e for e in captured if isinstance(e, CostIncurredEvent)]
    assert len(costs) == 1
    ev = costs[0]
    assert ev.provider == "tavily"
    assert ev.kind == "search"
    assert ev.units == 2
    assert ev.unit_cost_usd == pytest.approx(0.008)
    assert ev.cost_usd == pytest.approx(0.016)
    assert ev.pricing_source == "static"


@pytest.mark.asyncio
async def test_fetch_full_emits_one_cost_event(
    monkeypatch: pytest.MonkeyPatch, captured: list[BaseEvent]
) -> None:
    src = TavilySource(api_key="test")

    async def _stub_extract(**_: Any) -> dict[str, Any]:
        return {"results": [{"url": "https://x", "raw_content": "body"}]}

    monkeypatch.setattr(src._client, "extract", _stub_extract)

    await src.fetch_full("https://x")

    costs = [e for e in captured if isinstance(e, CostIncurredEvent)]
    assert len(costs) == 1
    assert costs[0].kind == "fetch"
    assert costs[0].provider == "tavily"
    assert costs[0].cost_usd == pytest.approx(0.016)

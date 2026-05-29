"""Tests for cost emission in ``WikipediaSource``."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from app.domain.events import BaseEvent, CostIncurredEvent
from app.llm.context import current_emitter
from app.sources.wikipedia import WikipediaSource


class _FakePage:
    def __init__(self, exists: bool = True) -> None:
        self._exists = exists
        self.fullurl = "https://en.wikipedia.org/wiki/Python"
        self.title = "Python"
        self.summary = "A snake / a language."
        self.text = "Long article body."
        self.links: dict[str, Any] = {}

    def exists(self) -> bool:
        return self._exists


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
async def test_search_emits_zero_cost_event(
    monkeypatch: pytest.MonkeyPatch, captured: list[BaseEvent]
) -> None:
    src = WikipediaSource()
    monkeypatch.setattr(src._wiki, "page", lambda _title: _FakePage())

    results = await src.search("Python", max_results=1)
    assert results

    costs = [e for e in captured if isinstance(e, CostIncurredEvent)]
    assert len(costs) == 1
    ev = costs[0]
    assert ev.provider == "wikipedia"
    assert ev.kind == "search"
    assert ev.units == 1
    assert ev.unit_cost_usd == 0.0
    assert ev.cost_usd == 0.0
    assert ev.pricing_source == "static"


@pytest.mark.asyncio
async def test_multiple_searches_emit_independent_events(
    monkeypatch: pytest.MonkeyPatch, captured: list[BaseEvent]
) -> None:
    src = WikipediaSource()
    monkeypatch.setattr(src._wiki, "page", lambda _title: _FakePage())

    await src.search("Python", max_results=1)
    await src.search("Rust", max_results=1)

    costs = [e for e in captured if isinstance(e, CostIncurredEvent)]
    assert len(costs) == 2
    assert all(c.cost_usd == 0.0 for c in costs)

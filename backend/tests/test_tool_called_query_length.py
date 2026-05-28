"""Tests for BRD-23 WP-4 ToolCalledEvent.query_length_tokens (AC-09, AC-10)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agent.run_state import RunState
from app.agent.tasks import search as search_mod
from app.agent.tasks.search import _count_query_tokens
from app.domain.enums import SourceType
from app.domain.events import (
    EvidenceAddedEvent,
    SubClaim,
    ToolCalledEvent,
)
from app.seams.source import SourceError, SourceResult
from app.sources import registry as registry_mod


class _FakeSource:
    def __init__(
        self,
        source_type: SourceType,
        results: list[SourceResult] | None = None,
        error: SourceError | None = None,
    ) -> None:
        self._st = source_type
        self._results = results or []
        self._error = error

    @property
    def source_type(self) -> SourceType:
        return self._st

    @property
    def name(self) -> str:
        return self._st.value

    async def search(
        self, query: str, max_results: int = 5, **_kwargs: object
    ) -> list[SourceResult]:
        if self._error is not None:
            raise self._error
        return self._results

    async def health_check(self) -> bool:
        return True


class _FakeRegistry:
    def __init__(self, sources: dict[SourceType, _FakeSource]) -> None:
        self._sources = sources

    def get(self, source_type: SourceType) -> _FakeSource:
        return self._sources[source_type]

    def types(self) -> list[SourceType]:
        return list(self._sources.keys())

    def all(self) -> list[_FakeSource]:
        return list(self._sources.values())


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    registry_mod._registry = None
    yield
    registry_mod._registry = None


def _state(question: str = "what is event sourcing") -> RunState:
    return RunState(
        run_id=uuid4(),
        question=question,
        sub_claims=[SubClaim(id="c1", text=question, status="pending")],
    )


def test_query_length_tokens_counts_whitespace_split_only() -> None:
    assert _count_query_tokens("event sourcing pattern") == 3
    assert _count_query_tokens("event   sourcing\tpattern") == 3
    assert _count_query_tokens("") == 0
    assert _count_query_tokens("one") == 1


@pytest.mark.asyncio
async def test_query_length_tokens_set_on_every_tool_called_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tavily = _FakeSource(
        SourceType.TAVILY,
        results=[SourceResult(url="https://x", title="t", snippet="s", relevance_score=0.9)],
    )
    monkeypatch.setattr(registry_mod, "_registry", _FakeRegistry({SourceType.TAVILY: tavily}))
    state = _state("what is event sourcing")
    events = await search_mod.execute_search_round(state)
    tool_events = [e for e in events if isinstance(e, ToolCalledEvent)]
    assert tool_events
    for ev in tool_events:
        assert ev.query_length_tokens is not None
        assert ev.query_length_tokens == len(ev.query.split())
    assert any(isinstance(e, EvidenceAddedEvent) for e in events)


def test_query_length_tokens_absent_on_pre_brd23_replay() -> None:
    """AC-09: a persisted event lacking the new fields must round-trip."""
    payload = {
        "type": "ToolCalled",
        "source_type": "tavily",
        "query": "pre brd 23",
        "query_intent": "verify c1",
        "target_claim_id": "c1",
    }
    ev = ToolCalledEvent.model_validate(payload)
    assert ev.query_length_tokens is None
    assert ev.tavily_days_filter is None


def test_tool_called_event_accepts_query_length_tokens_and_tavily_days_filter() -> None:
    ev = ToolCalledEvent(
        source_type=SourceType.TAVILY,
        query="a b c",
        query_intent="i",
        target_claim_id="c1",
        query_length_tokens=3,
        tavily_days_filter=180,
    )
    assert ev.query_length_tokens == 3
    assert ev.tavily_days_filter == 180

"""Tests for ``app.agent.tasks.search``."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agent.run_state import RunState
from app.agent.tasks import search as search_mod
from app.domain.enums import SourceType
from app.domain.events import (
    EvidenceAddedEvent,
    SourceFailedEvent,
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
        self._source_type = source_type
        self._results = results or []
        self._error = error
        self.calls: list[str] = []

    @property
    def source_type(self) -> SourceType:
        return self._source_type

    @property
    def name(self) -> str:
        return self._source_type.value

    async def search(self, query: str, max_results: int = 5) -> list[SourceResult]:
        self.calls.append(query)
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


def _state(num_claims: int = 1) -> RunState:
    return RunState(
        run_id=uuid4(),
        question="Q?",
        sub_claims=[
            SubClaim(id=f"c{i}", text=f"claim {i}", status="pending")
            for i in range(1, num_claims + 1)
        ],
    )


def _result(url: str, score: float = 0.8) -> SourceResult:
    return SourceResult(
        url=url,
        title=f"title-{url}",
        snippet=f"snippet for {url}",
        relevance_score=score,
    )


async def test_tavily_success_emits_tool_called_and_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tavily = _FakeSource(SourceType.TAVILY, results=[_result("u1"), _result("u2"), _result("u3")])
    monkeypatch.setattr(
        registry_mod,
        "_registry",
        _FakeRegistry(
            {SourceType.TAVILY: tavily, SourceType.WIKIPEDIA: _FakeSource(SourceType.WIKIPEDIA)}
        ),
    )
    state = _state()
    events = await search_mod.execute_search_round(state)

    tool_called = [e for e in events if isinstance(e, ToolCalledEvent)]
    evidence = [e for e in events if isinstance(e, EvidenceAddedEvent)]
    assert len(tool_called) == 1
    assert tool_called[0].source_type == SourceType.TAVILY
    assert len(evidence) == 3
    assert len(state.evidence) == 3
    assert all(ev.id == ei.event_id for ev, ei in zip(evidence, state.evidence, strict=True))


async def test_tavily_failure_cascades_to_wikipedia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tavily = _FakeSource(
        SourceType.TAVILY,
        error=SourceError(SourceType.TAVILY, "rate limit", recoverable=True),
    )
    wiki = _FakeSource(SourceType.WIKIPEDIA, results=[_result("w1"), _result("w2")])
    monkeypatch.setattr(
        registry_mod,
        "_registry",
        _FakeRegistry({SourceType.TAVILY: tavily, SourceType.WIKIPEDIA: wiki}),
    )
    state = _state()
    events = await search_mod.execute_search_round(state)

    tool_called = [e for e in events if isinstance(e, ToolCalledEvent)]
    failures = [e for e in events if isinstance(e, SourceFailedEvent)]
    evidence = [e for e in events if isinstance(e, EvidenceAddedEvent)]
    assert [t.source_type for t in tool_called] == [SourceType.TAVILY, SourceType.WIKIPEDIA]
    assert len(failures) == 1
    assert failures[0].source_type == SourceType.TAVILY
    assert len(evidence) == 2
    assert evidence[0].source_type == SourceType.WIKIPEDIA


async def test_both_sources_fail_no_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tavily = _FakeSource(
        SourceType.TAVILY,
        error=SourceError(SourceType.TAVILY, "fail1", recoverable=True),
    )
    wiki = _FakeSource(
        SourceType.WIKIPEDIA,
        error=SourceError(SourceType.WIKIPEDIA, "fail2", recoverable=True),
    )
    monkeypatch.setattr(
        registry_mod,
        "_registry",
        _FakeRegistry({SourceType.TAVILY: tavily, SourceType.WIKIPEDIA: wiki}),
    )
    state = _state()
    events = await search_mod.execute_search_round(state)

    failures = [e for e in events if isinstance(e, SourceFailedEvent)]
    evidence = [e for e in events if isinstance(e, EvidenceAddedEvent)]
    assert len(failures) == 2
    assert evidence == []
    assert len(state.failed_sources) == 2


async def test_cap_at_5_claims_per_round(monkeypatch: pytest.MonkeyPatch) -> None:
    tavily = _FakeSource(SourceType.TAVILY, results=[_result("u1")])
    monkeypatch.setattr(
        registry_mod,
        "_registry",
        _FakeRegistry({SourceType.TAVILY: tavily}),
    )
    state = _state(num_claims=7)
    events = await search_mod.execute_search_round(state)
    tool_called = [e for e in events if isinstance(e, ToolCalledEvent)]
    assert len(tool_called) == 5


async def test_unavailable_source_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    # Only Wikipedia registered; Tavily skipped in the cascade.
    wiki = _FakeSource(SourceType.WIKIPEDIA, results=[_result("w1")])
    monkeypatch.setattr(registry_mod, "_registry", _FakeRegistry({SourceType.WIKIPEDIA: wiki}))
    state = _state()
    events = await search_mod.execute_search_round(state)
    tool_called = [e for e in events if isinstance(e, ToolCalledEvent)]
    assert len(tool_called) == 1
    assert tool_called[0].source_type == SourceType.WIKIPEDIA

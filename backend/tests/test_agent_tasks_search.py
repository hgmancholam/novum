"""Tests for ``app.agent.tasks.search``."""

from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import pytest

from app.agent.run_state import RunState
from app.agent.tasks import search as search_mod
from app.domain.enums import SourceType
from app.domain.events import (
    EvidenceAddedEvent,
    QueryReformulatedEvent,
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

    async def search(
        self, query: str, max_results: int = 5, **_kwargs: object
    ) -> list[SourceResult]:
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
    # IP-31: Wikipedia is always invoked after Tavily for source heterogeneity.
    assert [t.source_type for t in tool_called] == [SourceType.TAVILY, SourceType.WIKIPEDIA]
    assert len(evidence) == 3
    assert all(e.source_type == SourceType.TAVILY for e in evidence)
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


async def test_empty_results_does_not_break_cascade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source returning [] (200 OK no matches) must fall through to next.

    Regression: academic-first questions where Semantic Scholar returns
    data:[] for full-claim queries dead-ended the cascade and emitted
    zero evidence. Cascade must only break on non-empty results.
    """
    tavily = _FakeSource(SourceType.TAVILY, results=[])  # 200 OK, no matches
    wiki = _FakeSource(SourceType.WIKIPEDIA, results=[_result("w1")])
    monkeypatch.setattr(
        registry_mod,
        "_registry",
        _FakeRegistry({SourceType.TAVILY: tavily, SourceType.WIKIPEDIA: wiki}),
    )
    state = _state()
    events = await search_mod.execute_search_round(state)

    tool_called = [e for e in events if isinstance(e, ToolCalledEvent)]
    evidence = [e for e in events if isinstance(e, EvidenceAddedEvent)]
    assert [t.source_type for t in tool_called] == [
        SourceType.TAVILY,
        SourceType.WIKIPEDIA,
    ]
    assert len(evidence) == 1
    assert evidence[0].source_type == SourceType.WIKIPEDIA


# =============================================================================
# IP-25 Phase 0: Parallel execution and query reformulation
# =============================================================================


async def test_execute_search_round_runs_claims_in_parallel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per-claim searches run concurrently; total time ≈ max(per-claim), not sum."""

    class _SlowSource(_FakeSource):
        def __init__(self, source_type: SourceType, delay: float) -> None:
            super().__init__(source_type, results=[_result("u1")])
            self.delay = delay

        async def search(
            self, query: str, max_results: int = 5, **_kwargs: object
        ) -> list[SourceResult]:
            await asyncio.sleep(self.delay)
            return await super().search(query, max_results, **_kwargs)

    # 3 claims with varying delays: 0.1s, 0.15s, 0.2s
    tavily = _SlowSource(SourceType.TAVILY, delay=0.2)
    monkeypatch.setattr(
        registry_mod, "_registry", _FakeRegistry({SourceType.TAVILY: tavily})
    )

    state = _state(num_claims=3)
    start = time.perf_counter()
    events = await search_mod.execute_search_round(state)
    elapsed = time.perf_counter() - start

    # Total time should be ~0.2s (max delay), not ~0.6s (sum)
    # Allow 50% overhead for test variance
    assert elapsed < 0.35, f"Expected parallel execution, got {elapsed:.3f}s"
    assert len([e for e in events if isinstance(e, EvidenceAddedEvent)]) == 3


async def test_execute_search_round_preserves_event_order_per_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Events within each claim are deterministic: ToolCalled before EvidenceAdded."""
    tavily = _FakeSource(SourceType.TAVILY, results=[_result("u1"), _result("u2")])
    monkeypatch.setattr(
        registry_mod, "_registry", _FakeRegistry({SourceType.TAVILY: tavily})
    )

    state = _state(num_claims=2)
    events = await search_mod.execute_search_round(state)

    # Each claim should emit: ToolCalled → EvidenceAdded (x2)
    # Total: 6 events (3 per claim)
    tool_calls = [e for e in events if isinstance(e, ToolCalledEvent)]
    evidence_adds = [e for e in events if isinstance(e, EvidenceAddedEvent)]

    assert len(tool_calls) == 2
    assert len(evidence_adds) == 4  # 2 results per claim

    # Find indices to check ordering within each claim
    for claim_id in ["c1", "c2"]:
        claim_events = [
            i
            for i, e in enumerate(events)
            if (
                isinstance(e, (ToolCalledEvent, EvidenceAddedEvent))
                and getattr(e, "target_claim_id", None) == claim_id
            )
        ]
        # First event for claim should be ToolCalled
        assert isinstance(events[claim_events[0]], ToolCalledEvent)


async def test_low_relevance_triggers_query_reformulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When all Tavily results have relevance_score < 0.3, reformulate and retry."""

    class _LowRelevanceSource(_FakeSource):
        def __init__(self) -> None:
            super().__init__(SourceType.TAVILY)
            self.call_count = 0

        async def search(
            self, query: str, max_results: int = 5, **_kwargs: object
        ) -> list[SourceResult]:
            self.call_count += 1
            if self.call_count == 1:
                # First call: all results below threshold
                return [
                    _result("u1", score=0.2),
                    _result("u2", score=0.15),
                    _result("u3", score=0.1),
                ]
            else:
                # Second call (reformulated): good results
                return [_result("u4", score=0.8)]

    tavily = _LowRelevanceSource()
    monkeypatch.setattr(
        registry_mod, "_registry", _FakeRegistry({SourceType.TAVILY: tavily})
    )

    state = _state()
    state.question = "What is the capital of France?"
    events = await search_mod.execute_search_round(state)

    # Should see: ToolCalled → QueryReformulated → ToolCalled → EvidenceAdded
    tool_calls = [e for e in events if isinstance(e, ToolCalledEvent)]
    reformulations = [e for e in events if isinstance(e, QueryReformulatedEvent)]
    evidence_adds = [e for e in events if isinstance(e, EvidenceAddedEvent)]

    assert len(tool_calls) == 2, "Expected 2 tool calls (original + reformulated)"
    assert len(reformulations) == 1, "Expected 1 reformulation"
    assert len(evidence_adds) == 1, "Expected evidence from reformulated query"

    # Check reformulation content
    reform_event = reformulations[0]
    assert reform_event.original_query == "claim 1"
    assert "claim 1" in reform_event.reformulated_query
    assert "What is the capital" in reform_event.reformulated_query
    assert reform_event.reason == "low_relevance"


async def test_high_relevance_skips_reformulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When at least one result has relevance_score ≥ 0.3, no reformulation."""
    tavily = _FakeSource(
        SourceType.TAVILY,
        results=[
            _result("u1", score=0.5),  # Above threshold
            _result("u2", score=0.2),
        ],
    )
    monkeypatch.setattr(
        registry_mod, "_registry", _FakeRegistry({SourceType.TAVILY: tavily})
    )

    state = _state()
    events = await search_mod.execute_search_round(state)

    tool_calls = [e for e in events if isinstance(e, ToolCalledEvent)]
    reformulations = [e for e in events if isinstance(e, QueryReformulatedEvent)]

    assert len(tool_calls) == 1, "Expected only 1 tool call (no reformulation)"
    assert len(reformulations) == 0, "Expected no reformulation"


# =============================================================================
# Cascade built from planner.preferred_sources (academic questions)
# =============================================================================


async def test_preferred_sources_override_cascade_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When state.preferred_sources is set, those sources are tried first."""
    s2 = _FakeSource(
        SourceType.SEMANTIC_SCHOLAR,
        results=[_result("s2-1"), _result("s2-2")],
    )
    tavily = _FakeSource(SourceType.TAVILY, results=[_result("t-1")])
    wiki = _FakeSource(SourceType.WIKIPEDIA, results=[_result("w-1")])
    monkeypatch.setattr(
        registry_mod,
        "_registry",
        _FakeRegistry(
            {
                SourceType.SEMANTIC_SCHOLAR: s2,
                SourceType.TAVILY: tavily,
                SourceType.WIKIPEDIA: wiki,
            }
        ),
    )
    state = _state()
    state.preferred_sources = ["semantic_scholar", "openalex"]

    events = await search_mod.execute_search_round(state)
    tool_called = [e.source_type for e in events if isinstance(e, ToolCalledEvent)]
    # IP-31: Wikipedia is always invoked at the end for source heterogeneity.
    assert tool_called == [SourceType.SEMANTIC_SCHOLAR, SourceType.WIKIPEDIA]
    assert s2.calls and not tavily.calls and wiki.calls


async def test_preferred_source_429_falls_back_to_default_cascade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If S2 rate-limits, the run falls back to Tavily then Wikipedia."""
    s2 = _FakeSource(
        SourceType.SEMANTIC_SCHOLAR,
        error=SourceError(
            SourceType.SEMANTIC_SCHOLAR,
            "Semantic Scholar rate-limited (HTTP 429)",
            recoverable=True,
        ),
    )
    tavily = _FakeSource(SourceType.TAVILY, results=[_result("t-1", score=0.9)])
    wiki = _FakeSource(SourceType.WIKIPEDIA, results=[_result("w-1")])
    monkeypatch.setattr(
        registry_mod,
        "_registry",
        _FakeRegistry(
            {
                SourceType.SEMANTIC_SCHOLAR: s2,
                SourceType.TAVILY: tavily,
                SourceType.WIKIPEDIA: wiki,
            }
        ),
    )
    state = _state()
    state.preferred_sources = ["semantic_scholar"]

    events = await search_mod.execute_search_round(state)
    tool_called = [e.source_type for e in events if isinstance(e, ToolCalledEvent)]
    failures = [e for e in events if isinstance(e, SourceFailedEvent)]
    evidence = [e for e in events if isinstance(e, EvidenceAddedEvent)]
    # S2 → fail → Tavily succeeds → Wikipedia always invoked (IP-31).
    assert tool_called == [
        SourceType.SEMANTIC_SCHOLAR,
        SourceType.TAVILY,
        SourceType.WIKIPEDIA,
    ]
    assert len(failures) == 1
    assert failures[0].source_type == SourceType.SEMANTIC_SCHOLAR
    # Tavily contributes 1 result, Wikipedia 1 more (IP-31 heterogeneity).
    assert [e.source_type for e in evidence] == [
        SourceType.TAVILY,
        SourceType.WIKIPEDIA,
    ]


async def test_empty_preferred_sources_uses_default_cascade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default behavior (no preferred_sources) is unchanged: Tavily first."""
    tavily = _FakeSource(SourceType.TAVILY, results=[_result("t-1")])
    wiki = _FakeSource(SourceType.WIKIPEDIA, results=[_result("w-1")])
    monkeypatch.setattr(
        registry_mod,
        "_registry",
        _FakeRegistry({SourceType.TAVILY: tavily, SourceType.WIKIPEDIA: wiki}),
    )
    state = _state()
    assert state.preferred_sources == []

    events = await search_mod.execute_search_round(state)
    tool_called = [e.source_type for e in events if isinstance(e, ToolCalledEvent)]
    # IP-31: Wikipedia is always invoked at the end for source heterogeneity.
    assert tool_called == [SourceType.TAVILY, SourceType.WIKIPEDIA]


# =============================================================================
# IP-30: domain-aware cascade skipping for non-academic domains
# =============================================================================


async def test_cascade_skips_academic_sources_for_geopolitics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Geopolitics questions skip S2/OpenAlex even when planner preferred them."""
    from app.domain.enums import QuestionDomain

    s2 = _FakeSource(SourceType.SEMANTIC_SCHOLAR, results=[_result("s2-1")])
    tavily = _FakeSource(SourceType.TAVILY, results=[_result("t-1")])
    wiki = _FakeSource(SourceType.WIKIPEDIA, results=[_result("w-1")])
    monkeypatch.setattr(
        registry_mod,
        "_registry",
        _FakeRegistry(
            {
                SourceType.SEMANTIC_SCHOLAR: s2,
                SourceType.TAVILY: tavily,
                SourceType.WIKIPEDIA: wiki,
            }
        ),
    )
    state = _state()
    state.preferred_sources = ["semantic_scholar"]
    state.domain = QuestionDomain.GEOPOLITICS

    events = await search_mod.execute_search_round(state)
    tool_called = [e.source_type for e in events if isinstance(e, ToolCalledEvent)]
    assert SourceType.SEMANTIC_SCHOLAR not in tool_called
    # IP-31: Wikipedia is always invoked at the end for source heterogeneity.
    assert tool_called == [SourceType.TAVILY, SourceType.WIKIPEDIA]
    assert not s2.calls


async def test_cascade_keeps_academic_sources_for_other_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Domains outside the skip-set keep S2/OpenAlex available."""
    from app.domain.enums import QuestionDomain

    s2 = _FakeSource(SourceType.SEMANTIC_SCHOLAR, results=[_result("s2-1")])
    tavily = _FakeSource(SourceType.TAVILY, results=[_result("t-1")])
    wiki = _FakeSource(SourceType.WIKIPEDIA, results=[_result("w-1")])
    monkeypatch.setattr(
        registry_mod,
        "_registry",
        _FakeRegistry(
            {
                SourceType.SEMANTIC_SCHOLAR: s2,
                SourceType.TAVILY: tavily,
                SourceType.WIKIPEDIA: wiki,
            }
        ),
    )
    state = _state()
    state.preferred_sources = ["semantic_scholar"]
    state.domain = QuestionDomain.MEDICAL

    events = await search_mod.execute_search_round(state)
    tool_called = [e.source_type for e in events if isinstance(e, ToolCalledEvent)]
    # IP-31: Wikipedia is always invoked at the end for source heterogeneity.
    assert tool_called == [SourceType.SEMANTIC_SCHOLAR, SourceType.WIKIPEDIA]

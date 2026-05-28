"""Unit tests for ``app.agent.tasks.deep_fetch`` (BRD-23 WP-2)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.agent.run_state import EvidenceItem, RunState
from app.agent.tasks.deep_fetch import (
    _count_deep_fetches,
    _deep_fetch_budget,
    maybe_deep_fetch,
)
from app.config import settings
from app.domain.enums import ComplexityHint, EventType, SourceType
from app.domain.events import DeepFetchPerformedEvent
from app.seams.source import SourceResult


class _StubSource:
    def __init__(self, *, content: str | None, raises: Exception | None = None) -> None:
        self._content = content
        self._raises = raises
        self.calls: list[str] = []

    @property
    def source_type(self) -> SourceType:
        return SourceType.TAVILY

    @property
    def name(self) -> str:
        return "stub"

    async def search(self, *args: Any, **kwargs: Any) -> list[SourceResult]:
        return []

    async def health_check(self) -> bool:
        return True

    async def fetch_full(self, url: str, *, timeout: float = 10.0) -> SourceResult | None:
        self.calls.append(url)
        if self._raises is not None:
            raise self._raises
        if self._content is None:
            return None
        return SourceResult(
            url=url, title="Stub", snippet=self._content[:100], content=self._content
        )


class _StubRegistry:
    def __init__(self, source: _StubSource) -> None:
        self._source = source

    def get(self, source_type: SourceType) -> Any:
        return self._source


def _make_state(
    *,
    complexity: ComplexityHint | None = ComplexityHint.STANDARD,
    evidence_text: str = "short snippet",
) -> RunState:
    state = RunState(run_id=uuid4(), question="q", complexity_hint=complexity)
    state.evidence.append(
        EvidenceItem(
            claim_id="c1",
            source_url="https://example.com/article",
            source_title="Title",
            text=evidence_text,
            polarity="supports",
            confidence=0.8,
        )
    )
    return state


def test_budget_table_matches_settings() -> None:
    assert _deep_fetch_budget(ComplexityHint.TRIVIAL) == settings.deep_fetch_max_per_run_trivial
    assert _deep_fetch_budget(ComplexityHint.STANDARD) == settings.deep_fetch_max_per_run_standard
    assert _deep_fetch_budget(ComplexityHint.DEEP) == settings.deep_fetch_max_per_run_deep
    assert _deep_fetch_budget(None) == settings.deep_fetch_max_per_run_standard


def test_count_uses_max_of_folded_and_live() -> None:
    state = _make_state()
    assert _count_deep_fetches(state) == 0
    state.metadata["deep_fetch_count_live"] = 2
    assert _count_deep_fetches(state) == 2
    state.events.append(
        DeepFetchPerformedEvent(
            source_type=SourceType.TAVILY,
            url="u",
            triggered_by_claim_id="c1",
            fetch_ms=1,
            content_length=0,
            success=False,
        )
    )
    assert _count_deep_fetches(state) == 2  # max(1 folded, 2 live)


@pytest.mark.asyncio
async def test_no_shallow_ids_is_noop() -> None:
    state = _make_state()
    emitted: list[DeepFetchPerformedEvent] = []
    advanced = await maybe_deep_fetch(
        state, [], registry=_StubRegistry(_StubSource(content="x")), emit=emitted.append
    )
    assert advanced is False
    assert emitted == []


@pytest.mark.asyncio
async def test_trivial_budget_zero_blocks_fetch() -> None:
    state = _make_state(complexity=ComplexityHint.TRIVIAL)
    emitted: list[DeepFetchPerformedEvent] = []

    async def _emit(ev: DeepFetchPerformedEvent) -> None:
        emitted.append(ev)

    advanced = await maybe_deep_fetch(
        state, ["c1"], registry=_StubRegistry(_StubSource(content="full")), emit=_emit
    )
    assert advanced is False
    assert emitted == []


@pytest.mark.asyncio
async def test_successful_fetch_updates_evidence_and_emits_success() -> None:
    state = _make_state()
    emitted: list[DeepFetchPerformedEvent] = []
    stub = _StubSource(content="full article body " * 20)

    async def _emit(ev: DeepFetchPerformedEvent) -> None:
        emitted.append(ev)

    advanced = await maybe_deep_fetch(
        state, ["c1"], registry=_StubRegistry(stub), emit=_emit
    )

    assert advanced is True
    assert stub.calls == ["https://example.com/article"]
    assert len(emitted) == 1
    ev = emitted[0]
    assert ev.type is EventType.DEEP_FETCH_PERFORMED
    assert ev.success is True
    assert ev.failure_reason is None
    assert ev.content_length > 0
    assert state.evidence[0].text.startswith("full article body")
    assert state.metadata["deep_fetch_count_live"] == 1


@pytest.mark.asyncio
async def test_failure_emits_failure_reason_and_keeps_evidence() -> None:
    state = _make_state()
    emitted: list[DeepFetchPerformedEvent] = []
    stub = _StubSource(content=None, raises=RuntimeError("nope"))

    async def _emit(ev: DeepFetchPerformedEvent) -> None:
        emitted.append(ev)

    advanced = await maybe_deep_fetch(
        state, ["c1"], registry=_StubRegistry(stub), emit=_emit
    )

    assert advanced is False
    assert len(emitted) == 1
    assert emitted[0].success is False
    assert emitted[0].failure_reason is not None
    assert "nope" in emitted[0].failure_reason
    assert state.evidence[0].text == "short snippet"


@pytest.mark.asyncio
async def test_skips_claims_with_long_evidence() -> None:
    state = _make_state(evidence_text="x" * (settings.deep_fetch_min_snippet_chars + 10))
    emitted: list[DeepFetchPerformedEvent] = []
    stub = _StubSource(content="ignored")
    advanced = await maybe_deep_fetch(
        state, ["c1"], registry=_StubRegistry(stub), emit=emitted.append
    )
    assert advanced is False
    assert stub.calls == []
    assert emitted == []

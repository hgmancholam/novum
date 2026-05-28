"""Tests for the Source seam (Protocol, SourceResult, SourceError)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.enums import SourceType
from app.seams.source import Source, SourceError, SourceResult


def test_source_result_is_frozen() -> None:
    result = SourceResult(url="https://x", title="t", snippet="s")
    with pytest.raises(ValidationError):
        result.url = "https://y"  # type: ignore[misc]


def test_source_result_serializes() -> None:
    result = SourceResult(
        url="https://x",
        title="t",
        snippet="s",
        content="c",
        relevance_score=0.5,
        published_date="2026-01-01",
    )
    dumped = result.model_dump()
    assert dumped == {
        "url": "https://x",
        "title": "t",
        "snippet": "s",
        "content": "c",
        "relevance_score": 0.5,
        "published_date": "2026-01-01",
    }
    assert SourceResult.model_validate(dumped) == result


def test_source_result_validates_relevance_score_range() -> None:
    with pytest.raises(ValidationError):
        SourceResult(url="u", title="t", snippet="s", relevance_score=-0.1)
    with pytest.raises(ValidationError):
        SourceResult(url="u", title="t", snippet="s", relevance_score=1.1)


def test_source_result_allows_optional_fields_none() -> None:
    result = SourceResult(url="u", title="t", snippet="s")
    assert result.content is None
    assert result.relevance_score is None
    assert result.published_date is None


def test_source_error_carries_metadata() -> None:
    err = SourceError(
        source_type=SourceType.TAVILY,
        message="boom",
        recoverable=False,
    )
    assert err.source_type is SourceType.TAVILY
    assert err.message == "boom"
    assert err.recoverable is False
    assert str(err) == "boom"


def test_source_error_default_recoverable_is_true() -> None:
    err = SourceError(source_type=SourceType.WIKIPEDIA, message="m")
    assert err.recoverable is True


def test_source_protocol_is_runtime_checkable() -> None:
    class _Fake:
        @property
        def source_type(self) -> SourceType:
            return SourceType.TAVILY

        @property
        def name(self) -> str:
            return "fake"

        async def search(
            self, query: str, max_results: int = 5, *, days: int | None = None
        ) -> list[SourceResult]:
            return []

        async def fetch_full(
            self, url: str, *, timeout: float = 10.0
        ) -> SourceResult | None:
            return None

        async def health_check(self) -> bool:
            return True

    fake = _Fake()
    assert isinstance(fake, Source)


def test_source_protocol_rejects_non_implementer() -> None:
    class _NotASource:
        pass

    assert not isinstance(_NotASource(), Source)

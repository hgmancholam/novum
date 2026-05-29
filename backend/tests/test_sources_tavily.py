"""Tests for TavilySource."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.domain.enums import SourceType
from app.seams.source import SourceError
from app.sources.base import DEFAULT_MAX_CONTENT_CHARS
from app.sources.tavily import TavilySource


def _make_source() -> TavilySource:
    source = TavilySource(api_key="test-key")
    return source


def _fake_response(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"results": items}


async def test_search_maps_api_response_to_source_results() -> None:
    source = _make_source()
    mock = AsyncMock(
        return_value=_fake_response(
            [
                {
                    "url": "https://a",
                    "title": "A",
                    "content": "snippet-a",
                    "raw_content": "raw-a",
                    "score": 0.9,
                    "published_date": "2026-01-01",
                },
                {
                    "url": "https://b",
                    "title": "B",
                    "content": "snippet-b",
                    "raw_content": "raw-b",
                    "score": 0.7,
                },
            ]
        )
    )
    source._client.search = mock  # type: ignore[method-assign]

    results = await source.search("topic", max_results=2)

    assert len(results) == 2
    assert results[0].url == "https://a"
    assert results[0].title == "A"
    assert results[0].snippet == "snippet-a"
    assert results[0].content == "raw-a"
    assert results[0].relevance_score == 0.9
    assert results[0].published_date == "2026-01-01"
    assert results[1].url == "https://b"
    assert results[1].published_date is None


async def test_search_truncates_content_to_5000_chars() -> None:
    source = _make_source()
    long_raw = "y" * (DEFAULT_MAX_CONTENT_CHARS + 100)
    mock = AsyncMock(
        return_value=_fake_response(
            [{"url": "u", "title": "t", "content": "s", "raw_content": long_raw}]
        )
    )
    source._client.search = mock  # type: ignore[method-assign]

    results = await source.search("q")
    assert results[0].content is not None
    assert results[0].content.endswith("...")
    assert len(results[0].content) == DEFAULT_MAX_CONTENT_CHARS + 3


async def test_search_clamps_max_results_between_1_and_20() -> None:
    source = _make_source()
    mock = AsyncMock(return_value=_fake_response([]))
    source._client.search = mock  # type: ignore[method-assign]

    await source.search("q", max_results=0)
    assert mock.call_args.kwargs["max_results"] == 1

    await source.search("q", max_results=999)
    assert mock.call_args.kwargs["max_results"] == 20

    await source.search("q", max_results=5)
    assert mock.call_args.kwargs["max_results"] == 5


async def test_search_passes_advanced_search_depth_and_includes_raw_content() -> None:
    source = _make_source()
    mock = AsyncMock(return_value=_fake_response([]))
    source._client.search = mock  # type: ignore[method-assign]

    await source.search("q", max_results=3)

    kwargs = mock.call_args.kwargs
    assert kwargs["search_depth"] == "advanced"
    assert kwargs["include_raw_content"] is True
    assert kwargs["include_answer"] is False
    assert kwargs["query"] == "q"


async def test_search_raises_source_error_on_client_exception() -> None:
    source = _make_source()
    original = RuntimeError("upstream down")
    mock = AsyncMock(side_effect=original)
    source._client.search = mock  # type: ignore[method-assign]

    with pytest.raises(SourceError) as exc_info:
        await source.search("q")

    assert exc_info.value.source_type is SourceType.TAVILY
    assert exc_info.value.recoverable is True
    assert exc_info.value.__cause__ is original


async def test_search_handles_empty_results_list() -> None:
    source = _make_source()
    source._client.search = AsyncMock(return_value={"results": []})  # type: ignore[method-assign]
    assert await source.search("q") == []


async def test_search_handles_missing_results_key() -> None:
    source = _make_source()
    source._client.search = AsyncMock(return_value={})  # type: ignore[method-assign]
    assert await source.search("q") == []


async def test_search_handles_missing_url_and_title_fields() -> None:
    source = _make_source()
    source._client.search = AsyncMock(  # type: ignore[method-assign]
        return_value=_fake_response([{"content": "c"}])
    )
    results = await source.search("q")
    assert results[0].url == ""
    assert results[0].title == ""
    assert results[0].snippet == "c"


async def test_health_check_returns_true_on_success() -> None:
    source = _make_source()
    source._client.search = AsyncMock(return_value={"results": []})  # type: ignore[method-assign]
    assert await source.health_check() is True


async def test_health_check_returns_false_on_exception() -> None:
    source = _make_source()
    source._client.search = AsyncMock(side_effect=RuntimeError("nope"))  # type: ignore[method-assign]
    assert await source.health_check() is False


def test_source_type_and_name_properties() -> None:
    source = _make_source()
    assert source.source_type is SourceType.TAVILY
    assert source.name == "Tavily Web Search"

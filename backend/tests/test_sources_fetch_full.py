"""Unit tests for ``TavilySource.fetch_full`` and ``WikipediaSource.fetch_full``.

BRD-23 WP-2 deep-fetch contract.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from app.sources.base import DEFAULT_MAX_CONTENT_CHARS
from app.sources.tavily import TavilySource
from app.sources.wikipedia import WikipediaSource


def _wiki_source(handler: Any) -> WikipediaSource:
    return WikipediaSource(transport=httpx.MockTransport(handler))


def _extracts_response(page: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json={"query": {"pages": {"0": page}}})


def _tavily() -> TavilySource:
    return TavilySource(api_key="test-key")


@pytest.mark.asyncio
async def test_tavily_fetch_full_returns_truncated_content() -> None:
    src = _tavily()
    big = "A" * (DEFAULT_MAX_CONTENT_CHARS * 4 + 500)
    payload: dict[str, Any] = {
        "results": [{"url": "https://x", "title": "T", "raw_content": big}]
    }
    src._client.extract = AsyncMock(return_value=payload)  # type: ignore[attr-defined]

    result = await src.fetch_full("https://x")

    assert result is not None
    assert result.title == "T"
    assert result.content is not None
    assert len(result.content) == DEFAULT_MAX_CONTENT_CHARS * 4 + 3  # "..."
    assert result.content.endswith("...")


@pytest.mark.asyncio
async def test_tavily_fetch_full_returns_none_on_empty_results() -> None:
    src = _tavily()
    src._client.extract = AsyncMock(return_value={"results": []})  # type: ignore[attr-defined]
    assert await src.fetch_full("https://x") is None


@pytest.mark.asyncio
async def test_tavily_fetch_full_returns_none_on_exception() -> None:
    src = _tavily()
    src._client.extract = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[attr-defined]
    assert await src.fetch_full("https://x") is None


@pytest.mark.asyncio
async def test_wikipedia_fetch_full_returns_truncated_content() -> None:
    long_text = "B" * (DEFAULT_MAX_CONTENT_CHARS * 4 + 200)

    def handler(request: httpx.Request) -> httpx.Response:
        return _extracts_response(
            {
                "title": "Foo",
                "extract": long_text,
                "fullurl": "https://en.wikipedia.org/wiki/Foo",
            }
        )

    src = _wiki_source(handler)
    result = await src.fetch_full("https://en.wikipedia.org/wiki/Foo")

    assert result is not None
    assert result.title == "Foo"
    assert result.content is not None
    assert result.content.endswith("...")


@pytest.mark.asyncio
async def test_wikipedia_fetch_full_returns_none_when_page_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _extracts_response({"title": "Missing", "missing": ""})

    src = _wiki_source(handler)
    assert await src.fetch_full("https://en.wikipedia.org/wiki/Missing") is None


@pytest.mark.asyncio
async def test_wikipedia_fetch_full_returns_none_on_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down")

    src = _wiki_source(handler)
    assert await src.fetch_full("https://en.wikipedia.org/wiki/Foo") is None

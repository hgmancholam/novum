"""Tests for WikipediaSource (MediaWiki Action API over httpx)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.domain.enums import SourceType
from app.seams.source import SourceError
from app.sources.wikipedia import WikipediaSource


def _search_payload(titles: list[str]) -> dict[str, Any]:
    return {
        "query": {
            "search": [{"title": t, "snippet": f"snippet for {t}"} for t in titles]
        }
    }


def _extracts_payload(pages: list[dict[str, Any]]) -> dict[str, Any]:
    return {"query": {"pages": {str(i): p for i, p in enumerate(pages)}}}


def _make_source(handler: Any, *, language: str = "en") -> WikipediaSource:
    return WikipediaSource(language=language, transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_returns_ranked_extracts() -> None:
    captured: dict[str, dict[str, str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        if params.get("list") == "search":
            captured["search"] = params
            return httpx.Response(200, json=_search_payload(["Python", "Java"]))
        captured["extracts"] = params
        return httpx.Response(
            200,
            json=_extracts_payload(
                [
                    {
                        "title": "Python",
                        "extract": "Python is a programming language.",
                        "fullurl": "https://en.wikipedia.org/wiki/Python",
                    },
                    {
                        "title": "Java",
                        "extract": "Java is an island and a language.",
                        "fullurl": "https://en.wikipedia.org/wiki/Java",
                    },
                ]
            ),
        )

    source = _make_source(handler)
    results = await source.search("programming languages", max_results=2)

    assert captured["search"]["srsearch"] == "programming languages"
    assert captured["search"]["srlimit"] == "2"
    assert "extracts" in captured["extracts"]["prop"]
    assert [r.title for r in results] == ["Python", "Java"]
    assert results[0].relevance_score == 1.0
    assert results[1].relevance_score == pytest.approx(0.9)
    assert results[0].content == "Python is a programming language."


@pytest.mark.asyncio
async def test_search_uses_language_hint_in_url() -> None:
    captured_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_hosts.append(request.url.host)
        if request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_payload(["Pitón"]))
        return httpx.Response(
            200,
            json=_extracts_payload(
                [
                    {
                        "title": "Pitón",
                        "extract": "Pitón es un lenguaje.",
                        "fullurl": "https://es.wikipedia.org/wiki/Pit%C3%B3n",
                    }
                ]
            ),
        )

    source = _make_source(handler)
    results = await source.search("pitón", max_results=1, language="es")

    assert all(h == "es.wikipedia.org" for h in captured_hosts)
    assert results[0].title == "Pitón"


@pytest.mark.asyncio
async def test_search_filters_disambiguation_pages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_payload(["Mercury", "Venus"]))
        return httpx.Response(
            200,
            json=_extracts_payload(
                [
                    {
                        "title": "Mercury",
                        "extract": "Could be many things.",
                        "fullurl": "https://en.wikipedia.org/wiki/Mercury",
                        "pageprops": {"disambiguation": ""},
                    },
                    {
                        "title": "Venus",
                        "extract": "Venus is a planet.",
                        "fullurl": "https://en.wikipedia.org/wiki/Venus",
                    },
                ]
            ),
        )

    source = _make_source(handler)
    results = await source.search("planet", max_results=2)

    assert [r.title for r in results] == ["Venus"]


@pytest.mark.asyncio
async def test_search_skips_missing_and_empty_pages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_payload(["Missing", "Empty", "Ok"]))
        return httpx.Response(
            200,
            json=_extracts_payload(
                [
                    {"title": "Missing", "missing": ""},
                    {
                        "title": "Empty",
                        "extract": "   ",
                        "fullurl": "https://en.wikipedia.org/wiki/Empty",
                    },
                    {
                        "title": "Ok",
                        "extract": "All good.",
                        "fullurl": "https://en.wikipedia.org/wiki/Ok",
                    },
                ]
            ),
        )

    source = _make_source(handler)
    results = await source.search("anything", max_results=3)

    assert [r.title for r in results] == ["Ok"]


@pytest.mark.asyncio
async def test_search_returns_empty_when_no_hits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"query": {"search": []}})

    source = _make_source(handler)
    assert await source.search("nothing matches xyz", max_results=3) == []


@pytest.mark.asyncio
async def test_search_raises_recoverable_on_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream down")

    source = _make_source(handler)
    with pytest.raises(SourceError) as excinfo:
        await source.search("foo")
    assert excinfo.value.source_type is SourceType.WIKIPEDIA
    assert excinfo.value.recoverable is True


@pytest.mark.asyncio
async def test_search_raises_non_recoverable_on_client_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    source = _make_source(handler)
    with pytest.raises(SourceError) as excinfo:
        await source.search("foo")
    assert excinfo.value.recoverable is False


@pytest.mark.asyncio
async def test_health_check_returns_true_on_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"query": {"search": []}})

    source = _make_source(handler)
    assert await source.health_check() is True


@pytest.mark.asyncio
async def test_health_check_returns_false_on_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    source = _make_source(handler)
    assert await source.health_check() is False


def test_source_type_and_name_properties() -> None:
    source = WikipediaSource(language="es")
    assert source.source_type is SourceType.WIKIPEDIA
    assert source.name == "Wikipedia (es)"


def test_unsupported_language_falls_back_to_english() -> None:
    source = WikipediaSource(language="zz")
    assert source.name == "Wikipedia (en)"

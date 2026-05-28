"""Tests for the OpenAlex source plugin."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.domain.enums import SourceType
from app.seams.source import SourceError
from app.sources.openalex import OpenAlexSource


def _mock_transport(handler):  # type: ignore[no-untyped-def]
    return httpx.MockTransport(handler)


def _search_payload(works: list[dict[str, Any]]) -> dict[str, Any]:
    return {"meta": {"count": len(works)}, "results": works}


# "Attention Is All You Need", OpenAlex W2963403868 (synthetic fixture).
# Abstract reconstructed from inverted index "We propose Transformer .".
WORK_FIXTURE: dict[str, Any] = {
    "id": "https://openalex.org/W2963403868",
    "doi": "https://doi.org/10.5555/3295222.3295349",
    "title": "Attention Is All You Need",
    "abstract_inverted_index": {
        "We": [0],
        "propose": [1],
        "Transformer": [2],
        ".": [3],
    },
    "publication_year": 2017,
    "publication_date": "2017-06-12",
    "authorships": [
        {"author": {"display_name": "Ashish Vaswani"}},
        {"author": {"display_name": "Noam Shazeer"}},
        {"author": {"display_name": "Niki Parmar"}},
        {"author": {"display_name": "Jakob Uszkoreit"}},
    ],
    "primary_location": {"source": {"display_name": "NeurIPS"}},
    "cited_by_count": 99999,
    "open_access": {"is_oa": True},
    "type": "article",
}


@pytest.mark.asyncio
async def test_search_parses_works_into_source_results() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([WORK_FIXTURE]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    results = await source.search("transformer architecture", max_results=3)

    assert "/works" in captured["url"]
    assert captured["params"]["search"] == "transformer architecture"
    assert captured["params"]["per_page"] == "3"
    assert "abstract_inverted_index" in captured["params"]["select"]
    assert len(results) == 1
    result = results[0]
    assert result.title == WORK_FIXTURE["title"]
    assert result.url == "https://doi.org/10.5555/3295222.3295349"
    assert "Vaswani" in result.snippet
    assert "NeurIPS" in result.snippet
    assert "cited 99999x" in result.snippet
    assert result.published_date == "2017-06-12"
    assert result.content == "We propose Transformer ."


@pytest.mark.asyncio
async def test_search_maps_days_to_from_publication_date() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    await source.search("ai safety", max_results=5, days=30)

    flt = captured["params"].get("filter", "")
    assert flt.startswith("from_publication_date:")
    # ISO date YYYY-MM-DD
    assert len(flt.split(":", 1)[1]) == 10


@pytest.mark.asyncio
async def test_search_omits_filter_when_days_is_none() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    await source.search("history of computation", max_results=2)

    assert "filter" not in captured["params"]


@pytest.mark.asyncio
async def test_search_uses_openalex_url_when_doi_missing() -> None:
    work = dict(WORK_FIXTURE)
    work["doi"] = ""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_search_payload([work]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    [result] = await source.search("foo", max_results=1)

    assert result.url == "https://openalex.org/W2963403868"


@pytest.mark.asyncio
async def test_search_falls_back_to_year_when_publication_date_missing() -> None:
    work = dict(WORK_FIXTURE)
    work["publication_date"] = None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_search_payload([work]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    [result] = await source.search("foo", max_results=1)

    assert result.published_date == "2017-01-01"


@pytest.mark.asyncio
async def test_search_handles_missing_abstract() -> None:
    work = dict(WORK_FIXTURE)
    work["abstract_inverted_index"] = None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_search_payload([work]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    [result] = await source.search("foo", max_results=1)

    assert result.content is None
    # Snippet still includes the prefix + title fallback body.
    assert "Attention" in result.snippet


@pytest.mark.asyncio
async def test_search_raises_recoverable_on_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    source = OpenAlexSource(transport=_mock_transport(handler))
    with pytest.raises(SourceError) as excinfo:
        await source.search("foo")
    assert excinfo.value.recoverable is True
    assert excinfo.value.source_type == SourceType.OPENALEX


@pytest.mark.asyncio
async def test_search_raises_recoverable_on_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"error": "down"})

    source = OpenAlexSource(transport=_mock_transport(handler))
    with pytest.raises(SourceError) as excinfo:
        await source.search("foo")
    assert excinfo.value.recoverable is True


@pytest.mark.asyncio
async def test_search_raises_non_recoverable_on_client_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad query"})

    source = OpenAlexSource(transport=_mock_transport(handler))
    with pytest.raises(SourceError) as excinfo:
        await source.search("foo")
    assert excinfo.value.recoverable is False


@pytest.mark.asyncio
async def test_search_sends_mailto_when_email_configured() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(
        email="novum@example.com", transport=_mock_transport(handler)
    )
    await source.search("foo")
    assert captured["params"].get("mailto") == "novum@example.com"


@pytest.mark.asyncio
async def test_search_omits_mailto_when_email_blank() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(email="", transport=_mock_transport(handler))
    await source.search("foo")
    assert "mailto" not in captured["params"]


@pytest.mark.asyncio
async def test_search_sends_api_key_as_query_param() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(
        api_key="secret-key", transport=_mock_transport(handler)
    )
    await source.search("foo")
    assert captured["params"].get("api_key") == "secret-key"


@pytest.mark.asyncio
async def test_search_omits_api_key_when_anonymous() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(api_key="", transport=_mock_transport(handler))
    await source.search("foo")
    assert "api_key" not in captured["params"]


@pytest.mark.asyncio
async def test_fetch_full_resolves_openalex_id() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json=WORK_FIXTURE)

    source = OpenAlexSource(transport=_mock_transport(handler))
    result = await source.fetch_full("https://openalex.org/W2963403868")

    assert result is not None
    assert "W2963403868" in captured["path"]
    assert result.title == WORK_FIXTURE["title"]


@pytest.mark.asyncio
async def test_fetch_full_resolves_doi_url() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json=WORK_FIXTURE)

    source = OpenAlexSource(transport=_mock_transport(handler))
    result = await source.fetch_full("https://doi.org/10.5555/3295222.3295349")

    assert result is not None
    assert "doi:" in captured["path"]


@pytest.mark.asyncio
async def test_fetch_full_returns_none_for_unrelated_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("should not be called")

    source = OpenAlexSource(transport=_mock_transport(handler))
    assert await source.fetch_full("https://arxiv.org/abs/1706.03762") is None


def test_source_type_and_name() -> None:
    source = OpenAlexSource()
    assert source.source_type == SourceType.OPENALEX
    assert source.name == "OpenAlex"


def test_reconstruct_abstract_orders_by_position() -> None:
    inverted = {"world": [1], "Hello": [0], "!": [2]}
    assert OpenAlexSource._reconstruct_abstract(inverted) == "Hello world !"


def test_reconstruct_abstract_empty() -> None:
    assert OpenAlexSource._reconstruct_abstract(None) == ""
    assert OpenAlexSource._reconstruct_abstract({}) == ""


def test_extract_work_id_handles_known_hosts() -> None:
    extract = OpenAlexSource._extract_work_id
    assert extract("https://openalex.org/W2963403868") == "W2963403868"
    assert extract("https://api.openalex.org/works/W123") == "W123"
    assert extract("https://doi.org/10.1234/example") == "doi:10.1234/example"
    assert extract("https://example.com/paper/abc") is None

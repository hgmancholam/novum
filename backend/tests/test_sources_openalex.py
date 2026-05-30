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


async def _no_sleep(_seconds: float) -> None:
    """Bypass real backoff in retry tests."""
    return None


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
    assert "search" not in captured["params"]
    flt = captured["params"]["filter"]
    assert "title_and_abstract.search:transformer architecture" in flt
    assert "is_retracted:false" in flt
    assert "is_paratext:false" in flt
    assert "has_abstract:true" in flt
    assert "type:article|review" in flt
    assert captured["params"]["sort"] == "relevance_score:desc,cited_by_count:desc"
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
    # Filter is now a comma-separated list — the from_publication_date
    # token appears among the quality filters.
    tokens = flt.split(",")
    date_tokens = [t for t in tokens if t.startswith("from_publication_date:")]
    assert len(date_tokens) == 1
    # ISO date YYYY-MM-DD
    assert len(date_tokens[0].split(":", 1)[1]) == 10


@pytest.mark.asyncio
async def test_search_omits_filter_when_days_is_none() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    await source.search("history of computation", max_results=2)

    # Even without ``days``, the filter is always present because the
    # quality filters (is_retracted, is_paratext, etc.) are mandatory.
    flt = captured["params"]["filter"]
    assert "from_publication_date:" not in flt
    assert "is_retracted:false" in flt


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
async def test_search_raises_recoverable_on_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two consecutive 429s exhaust the single retry and raise SourceError."""
    monkeypatch.setattr("app.sources.openalex.asyncio.sleep", _no_sleep)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json={"error": "rate limited"})

    source = OpenAlexSource(transport=_mock_transport(handler))
    with pytest.raises(SourceError) as excinfo:
        await source.search("foo")
    assert excinfo.value.recoverable is True
    assert excinfo.value.source_type == SourceType.OPENALEX
    assert calls == 2, "expected one retry after the initial 429"


@pytest.mark.asyncio
async def test_search_retries_once_on_429_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient 429 followed by 200 recovers without raising."""
    monkeypatch.setattr("app.sources.openalex.asyncio.sleep", _no_sleep)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json=_search_payload([WORK_FIXTURE]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    results = await source.search("foo", max_results=1)
    assert calls == 2
    assert len(results) == 1
    assert results[0].title == WORK_FIXTURE["title"]


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


def test_citation_bump_is_log_scaled_and_capped() -> None:
    """C6: same shape as SemanticScholar — 0 at 0, monotonic, capped at +0.30."""
    from app.sources.openalex import _citation_bump

    assert _citation_bump(0) == 0.0
    assert _citation_bump(-1) == 0.0
    assert _citation_bump(10) < _citation_bump(100) < _citation_bump(1000)
    assert _citation_bump(1000) == pytest.approx(0.30, abs=0.005)
    assert _citation_bump(1_000_000) == pytest.approx(0.30, abs=0.005)


@pytest.mark.asyncio
async def test_search_relevance_score_lifts_well_cited_work() -> None:
    """C6: at the same rank, a highly cited OpenAlex work outscores a
    0-cite work. We push the target to rank 5 (base 0.75) so the +0.30
    citation bump is observable after the [0.0, 1.0] clamp.
    """
    cited = dict(WORK_FIXTURE)  # cited_by_count=99999
    uncited = dict(WORK_FIXTURE)
    uncited["id"] = "https://openalex.org/W0"
    uncited["title"] = "Obscure work"
    uncited["cited_by_count"] = 0

    pad = [
        dict(WORK_FIXTURE, id=f"https://openalex.org/Wpad{i}", title=f"pad {i}")
        for i in range(5)
    ]

    def handler_factory(target: dict[str, Any]):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_search_payload(pad + [target]))

        return handler

    src_cited = OpenAlexSource(transport=_mock_transport(handler_factory(cited)))
    src_uncited = OpenAlexSource(transport=_mock_transport(handler_factory(uncited)))
    cited_results = await src_cited.search("q", max_results=6)
    uncited_results = await src_uncited.search("q", max_results=6)
    assert cited_results[5].relevance_score > uncited_results[5].relevance_score
    assert cited_results[5].relevance_score <= 1.0


@pytest.mark.asyncio
async def test_search_appends_language_filter_from_hint() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    await source.search("inteligencia artificial", max_results=2, language="es")

    flt = captured["params"]["filter"]
    assert "language:es" in flt


@pytest.mark.asyncio
async def test_search_ignores_unsupported_language_hint() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    await source.search("foo", max_results=2, language="")

    flt = captured["params"]["filter"]
    assert "language:" not in flt


@pytest.mark.asyncio
async def test_search_replaces_commas_in_query_to_avoid_filter_collision() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    await source.search("foo, bar, baz", max_results=1)

    flt = captured["params"]["filter"]
    assert "title_and_abstract.search:foo  bar  baz" in flt


@pytest.mark.asyncio
async def test_search_applies_citation_floor_for_deep_state_of_art() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    await source.search(
        "q",
        max_results=3,
        question_type="state_of_art",
        complexity_hint="deep",
    )

    assert "cited_by_count:>10" in captured["params"]["filter"]


@pytest.mark.asyncio
async def test_search_omits_citation_floor_outside_deep_state_of_art() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    # state_of_art alone (no deep) → no floor
    await source.search(
        "q",
        max_results=3,
        question_type="state_of_art",
        complexity_hint="standard",
    )
    assert "cited_by_count:>10" not in captured["params"]["filter"]

    # deep but causal → no floor
    await source.search(
        "q",
        max_results=3,
        question_type="causal",
        complexity_hint="deep",
    )
    assert "cited_by_count:>10" not in captured["params"]["filter"]


@pytest.mark.asyncio
async def test_search_maps_domain_to_concepts_filter() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    await source.search("q", max_results=3, domain="medical")

    assert "concepts.id:C71924100" in captured["params"]["filter"]


@pytest.mark.asyncio
async def test_search_omits_concepts_filter_for_unmapped_domain() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = OpenAlexSource(transport=_mock_transport(handler))
    await source.search("q", max_results=3, domain="lifestyle")

    assert "concepts.id:" not in captured["params"]["filter"]
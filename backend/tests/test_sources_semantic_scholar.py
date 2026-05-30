"""Tests for the Semantic Scholar source plugin."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.domain.enums import SourceType
from app.seams.source import SourceError
from app.sources.semantic_scholar import SemanticScholarSource


def _mock_transport(handler):  # type: ignore[no-untyped-def]
    return httpx.MockTransport(handler)


async def _no_sleep(_seconds: float) -> None:
    """Bypass real backoff in retry tests."""
    return None


def _search_payload(papers: list[dict[str, Any]]) -> dict[str, Any]:
    return {"total": len(papers), "offset": 0, "data": papers}


PAPER_FIXTURE = {
    "paperId": "abc123",
    "title": "Attention Is All You Need",
    "abstract": "We propose a new simple network architecture, the Transformer.",
    "url": "https://www.semanticscholar.org/paper/abc123",
    "year": 2017,
    "publicationDate": "2017-06-12",
    "authors": [
        {"name": "Ashish Vaswani"},
        {"name": "Noam Shazeer"},
        {"name": "Niki Parmar"},
        {"name": "Jakob Uszkoreit"},
    ],
    "venue": "NeurIPS",
    "citationCount": 12345,
    "externalIds": {"DOI": "10.5555/3295222.3295349", "ArXiv": "1706.03762"},
    "openAccessPdf": {"url": "https://arxiv.org/pdf/1706.03762"},
}


@pytest.mark.asyncio
async def test_search_parses_papers_into_source_results() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([PAPER_FIXTURE]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    results = await source.search("transformer architecture", max_results=3)

    assert "paper/search" in captured["url"]
    assert captured["params"]["query"] == "transformer architecture"
    assert captured["params"]["limit"] == "3"
    assert "abstract" in captured["params"]["fields"]
    assert len(results) == 1
    result = results[0]
    assert result.url == PAPER_FIXTURE["url"]
    assert result.title == PAPER_FIXTURE["title"]
    assert "Vaswani" in result.snippet
    assert "cited 12345x" in result.snippet
    assert result.published_date == "2017-06-12"
    assert result.content is not None and "Transformer" in result.content


@pytest.mark.asyncio
async def test_search_maps_days_to_year_range() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    await source.search("ai safety", max_results=5, days=730)

    year = captured["params"].get("year")
    assert year is not None
    # Either a single year (if window stays inside current year) or a range.
    assert "-" in year or year.isdigit()


@pytest.mark.asyncio
async def test_search_omits_year_when_days_is_none() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    await source.search("history of computation", max_results=2)

    assert "year" not in captured["params"]


@pytest.mark.asyncio
async def test_search_falls_back_to_doi_url_when_url_missing() -> None:
    paper = dict(PAPER_FIXTURE)
    paper["url"] = ""
    paper["externalIds"] = {"DOI": "10.1234/example"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_search_payload([paper]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    [result] = await source.search("foo", max_results=1)

    assert result.url == "https://doi.org/10.1234/example"


@pytest.mark.asyncio
async def test_search_falls_back_to_year_when_publication_date_missing() -> None:
    paper = dict(PAPER_FIXTURE)
    paper["publicationDate"] = None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_search_payload([paper]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    [result] = await source.search("foo", max_results=1)

    assert result.published_date == "2017-01-01"


@pytest.mark.asyncio
async def test_search_raises_recoverable_on_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two consecutive 429s exhaust the single retry and raise SourceError."""
    monkeypatch.setattr(
        "app.sources.semantic_scholar.asyncio.sleep",
        _no_sleep,
    )
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json={"error": "rate limited"})

    source = SemanticScholarSource(transport=_mock_transport(handler))
    with pytest.raises(SourceError) as excinfo:
        await source.search("foo")
    assert excinfo.value.recoverable is True
    assert excinfo.value.source_type == SourceType.SEMANTIC_SCHOLAR
    assert calls == 2, "expected one retry after the initial 429"


@pytest.mark.asyncio
async def test_search_retries_once_on_429_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient 429 followed by 200 recovers without raising."""
    monkeypatch.setattr(
        "app.sources.semantic_scholar.asyncio.sleep",
        _no_sleep,
    )
    calls = 0
    paper = dict(PAPER_FIXTURE)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json=_search_payload([paper]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    results = await source.search("foo", max_results=1)
    assert calls == 2
    assert len(results) == 1
    assert results[0].title == paper["title"]


@pytest.mark.asyncio
async def test_search_raises_recoverable_on_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "down"})

    source = SemanticScholarSource(transport=_mock_transport(handler))
    with pytest.raises(SourceError) as excinfo:
        await source.search("foo")
    assert excinfo.value.recoverable is True


@pytest.mark.asyncio
async def test_search_raises_non_recoverable_on_client_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad query"})

    source = SemanticScholarSource(transport=_mock_transport(handler))
    with pytest.raises(SourceError) as excinfo:
        await source.search("foo")
    assert excinfo.value.recoverable is False


@pytest.mark.asyncio
async def test_search_sends_x_api_key_header_when_configured() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json=_search_payload([]))

    source = SemanticScholarSource(
        api_key="secret-key", transport=_mock_transport(handler)
    )
    await source.search("foo")
    assert captured["headers"].get("x-api-key") == "secret-key"


@pytest.mark.asyncio
async def test_search_omits_x_api_key_header_when_anonymous() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json=_search_payload([]))

    source = SemanticScholarSource(api_key="", transport=_mock_transport(handler))
    await source.search("foo")
    assert "x-api-key" not in {k.lower() for k in captured["headers"]}


@pytest.mark.asyncio
async def test_fetch_full_resolves_paper_id_and_returns_result_with_tldr() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                **PAPER_FIXTURE,
                "tldr": {"text": "Transformers are great."},
            },
        )

    source = SemanticScholarSource(transport=_mock_transport(handler))
    result = await source.fetch_full(
        "https://www.semanticscholar.org/paper/abc123"
    )

    assert result is not None
    assert "abc123" in captured["path"]
    assert "tldr" in captured["params"]["fields"]
    assert result.content is not None and result.content.startswith("TL;DR")


@pytest.mark.asyncio
async def test_fetch_full_returns_none_for_unrelated_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("should not be called")

    source = SemanticScholarSource(transport=_mock_transport(handler))
    assert await source.fetch_full("https://arxiv.org/abs/1706.03762") is None


def test_source_type_and_name() -> None:
    source = SemanticScholarSource()
    assert source.source_type == SourceType.SEMANTIC_SCHOLAR
    assert source.name == "Semantic Scholar"


def test_extract_paper_id_strips_path() -> None:
    extract = SemanticScholarSource._extract_paper_id
    assert extract("https://www.semanticscholar.org/paper/abc123") == "abc123"
    assert extract("https://api.semanticscholar.org/graph/v1/paper/xyz") == "xyz"
    assert extract("https://example.com/paper/abc") is None


def test_search_payload_helper_round_trip() -> None:
    payload = _search_payload([PAPER_FIXTURE])
    encoded = json.dumps(payload)
    assert json.loads(encoded)["data"][0]["paperId"] == "abc123"


def test_citation_bump_is_log_scaled_and_capped() -> None:
    """C6: citation bump must be 0 at 0 cites, monotonic up, capped at +0.30."""
    from app.sources.semantic_scholar import _citation_bump

    assert _citation_bump(0) == 0.0
    assert _citation_bump(-5) == 0.0
    b10 = _citation_bump(10)
    b100 = _citation_bump(100)
    b1000 = _citation_bump(1000)
    b1_000_000 = _citation_bump(1_000_000)
    assert 0.0 < b10 < b100 < b1000
    assert b1000 == pytest.approx(0.30, abs=0.005)
    # Hard cap at +0.30 — extreme citation counts cannot dominate scoring.
    assert b1_000_000 == pytest.approx(0.30, abs=0.005)


@pytest.mark.asyncio
async def test_search_relevance_score_lifts_well_cited_paper() -> None:
    """C6: at the same rank position, a well-cited paper outscores an
    uncited paper because the log-scaled citation bump differentiates
    them. We push the target to rank 5 (base 0.75) so the +0.30 bump is
    observable after the [0.0, 1.0] clamp.
    """
    cited = dict(PAPER_FIXTURE)  # citationCount=12345
    uncited = dict(PAPER_FIXTURE)
    uncited["paperId"] = "zero1"
    uncited["title"] = "Obscure paper"
    uncited["citationCount"] = 0

    pad = [dict(PAPER_FIXTURE, paperId=f"p{i}", title=f"pad {i}") for i in range(5)]

    def handler_factory(target: dict[str, Any]):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_search_payload(pad + [target]))

        return handler

    src_cited = SemanticScholarSource(transport=_mock_transport(handler_factory(cited)))
    src_uncited = SemanticScholarSource(
        transport=_mock_transport(handler_factory(uncited))
    )
    cited_results = await src_cited.search("q", max_results=6)
    uncited_results = await src_uncited.search("q", max_results=6)
    # Target is at index 5 in both lists.
    assert cited_results[5].relevance_score > uncited_results[5].relevance_score
    assert cited_results[5].relevance_score <= 1.0


@pytest.mark.asyncio
async def test_search_maps_question_type_to_publication_types() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    await source.search("q", max_results=3, question_type="state_of_art")

    assert captured["params"]["publicationTypes"] == "Review,MetaAnalysis"


@pytest.mark.asyncio
async def test_search_maps_expected_experts_to_fields_of_study() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    await source.search(
        "q",
        max_results=3,
        expected_experts=["medical_researcher"],
    )

    fields = captured["params"]["fieldsOfStudy"].split(",")
    assert "Medicine" in fields
    assert "Biology" in fields


@pytest.mark.asyncio
async def test_search_omits_hint_params_when_unknown() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    await source.search(
        "q",
        max_results=3,
        question_type="not_a_real_type",
        expected_experts=["nobody"],
    )

    assert "publicationTypes" not in captured["params"]
    assert "fieldsOfStudy" not in captured["params"]


@pytest.mark.asyncio
async def test_search_applies_min_citation_count_for_deep_state_of_art() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    await source.search(
        "q",
        max_results=3,
        question_type="state_of_art",
        complexity_hint="deep",
    )

    assert captured["params"]["minCitationCount"] == "10"


@pytest.mark.asyncio
async def test_search_omits_min_citation_count_outside_deep_state_of_art() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    # state_of_art but only standard complexity → no floor
    await source.search(
        "q",
        max_results=3,
        question_type="state_of_art",
        complexity_hint="standard",
    )
    assert "minCitationCount" not in captured["params"]

    # deep but causal → no floor
    await source.search(
        "q",
        max_results=3,
        question_type="causal",
        complexity_hint="deep",
    )
    assert "minCitationCount" not in captured["params"]


@pytest.mark.asyncio
async def test_search_maps_domain_to_fields_of_study() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    await source.search("q", max_results=3, domain="medical")

    assert captured["params"]["fieldsOfStudy"] == "Medicine,Biology"


@pytest.mark.asyncio
async def test_search_prefers_domain_over_expected_experts() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    await source.search(
        "q",
        max_results=3,
        domain="medical",
        expected_experts=["practitioner_engineer"],
    )

    # Domain (Medicine,Biology) wins; engineer mapping is ignored.
    assert captured["params"]["fieldsOfStudy"] == "Medicine,Biology"


@pytest.mark.asyncio
async def test_search_falls_back_to_experts_when_domain_is_other() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_payload([]))

    source = SemanticScholarSource(transport=_mock_transport(handler))
    await source.search(
        "q",
        max_results=3,
        domain="other",
        expected_experts=["industry_analyst"],
    )

    assert captured["params"]["fieldsOfStudy"] == "Economics,Business"

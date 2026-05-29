"""Semantic Scholar Graph API source.

Provides peer-reviewed and preprint academic literature with citation
metadata. The free tier requires no API key; requests should stay under
~1 RPS without one. An optional ``S2_API_KEY`` raises the limit.

The recency filter (``days``) is mapped to Semantic Scholar's ``year``
range parameter, since the API does not accept day-level filters.
"""

from __future__ import annotations

import asyncio
import math
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
import httpx
import structlog

from app.config import settings
from app.domain.enums import SourceType
from app.seams.source import SourceError, SourceResult
from app.sources._cost import emit_source_cost
from app.sources.base import DEFAULT_MAX_CONTENT_CHARS, BaseSource
from app.sources.pricing import free_source_cost

logger = structlog.get_logger(__name__)

_BASE_URL = "https://api.semanticscholar.org/graph/v1"
_SEARCH_FIELDS = (
    "title,abstract,url,year,publicationDate,authors.name,venue,"
    "citationCount,influentialCitationCount,externalIds,openAccessPdf"
)


def _citation_bump(citation_count: int) -> float:
    """C6: log-scaled relevance bump from citation count.

    Caps at +0.30 at ~1000 citations and degrades smoothly to 0 at 0
    citations. Same formula is used by OpenAlex so academic results from
    either source can be compared on a single relevance scale.
    """
    if citation_count <= 0:
        return 0.0
    return min(0.30, math.log10(1 + citation_count) / math.log10(1001) * 0.30)


class SemanticScholarSource(BaseSource):
    """Semantic Scholar Graph API client.

    Optional ``transport`` lets tests inject ``httpx.MockTransport``.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        configured = api_key
        if configured is None:
            secret = getattr(settings, "semantic_scholar_api_key", None)
            configured = secret.get_secret_value() if secret is not None else None
        self._api_key = configured or None
        self._transport = transport
        self._timeout = timeout

    @property
    def source_type(self) -> SourceType:
        return SourceType.SEMANTIC_SCHOLAR

    @property
    def name(self) -> str:
        return "Semantic Scholar"

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": "Novum/1.0 (research agent; contact: novum@duckdns.org)"}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    def _client(self) -> httpx.AsyncClient:
        kwargs: dict[str, Any] = {"timeout": self._timeout, "headers": self._headers()}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    @staticmethod
    def _year_range_from_days(days: int | None) -> str | None:
        if days is None or days <= 0:
            return None
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=days)
        if start.year == today.year:
            return str(today.year)
        return f"{start.year}-{today.year}"

    @staticmethod
    def _paper_to_result(paper: dict[str, Any], relevance_score: float) -> SourceResult:
        title = (paper.get("title") or "").strip() or "(untitled)"
        abstract = (paper.get("abstract") or "").strip()
        url = paper.get("url") or ""
        external = paper.get("externalIds") or {}
        if not url and "DOI" in external:
            url = f"https://doi.org/{external['DOI']}"
        if not url:
            paper_id = paper.get("paperId") or ""
            url = f"https://www.semanticscholar.org/paper/{paper_id}"

        published_date = paper.get("publicationDate")
        if not published_date and paper.get("year"):
            published_date = f"{paper['year']}-01-01"

        authors = ", ".join(
            a.get("name", "") for a in (paper.get("authors") or [])[:3] if a.get("name")
        )
        venue = paper.get("venue") or ""
        citation_count = paper.get("citationCount") or 0
        prefix_parts = [p for p in [authors, venue, f"cited {citation_count}x"] if p]
        prefix = " — ".join(prefix_parts)
        snippet_body = abstract or title
        snippet = (f"[{prefix}] {snippet_body}" if prefix else snippet_body)[:500]

        content = abstract if abstract else None
        if content and len(content) > DEFAULT_MAX_CONTENT_CHARS:
            content = content[:DEFAULT_MAX_CONTENT_CHARS] + "..."

        # C6: citation-weighted ranking. A log-scaled bump (capped at +0.3
        # at ~1000 citations) lifts well-cited papers above rank-only
        # peers so the dedup/scoring layer surfaces them first.
        adjusted_relevance = min(
            1.0,
            relevance_score + _citation_bump(citation_count),
        )

        return SourceResult(
            url=url,
            title=title,
            snippet=snippet,
            content=content,
            relevance_score=adjusted_relevance,
            published_date=published_date,
        )

    async def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        days: int | None = None,
    ) -> list[SourceResult]:
        limit = max(1, min(max_results, 20))
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "fields": _SEARCH_FIELDS,
        }
        year = self._year_range_from_days(days)
        if year is not None:
            params["year"] = year

        logger.debug(
            "semantic_scholar_search_start", query=query, limit=limit, year=year
        )
        # One retry on 429 with a short backoff: S2's per-IP window often
        # clears within ~1 s and a single retry recovers a meaningful
        # fraction of rate-limited calls without stalling the round.
        response: httpx.Response | None = None
        for attempt in range(2):
            try:
                async with self._client() as client:
                    response = await client.get(
                        f"{_BASE_URL}/paper/search", params=params
                    )
            except httpx.HTTPError as exc:
                logger.error("semantic_scholar_search_error", query=query, error=str(exc))
                raise SourceError(
                    source_type=self.source_type,
                    message="Semantic Scholar request failed",
                    recoverable=True,
                ) from exc
            if response.status_code != 429 or attempt == 1:
                break
            logger.warning(
                "semantic_scholar_rate_limited_retry", query=query, attempt=attempt + 1
            )
            await asyncio.sleep(1.0)

        assert response is not None  # loop always assigns or raises
        if response.status_code == 429:
            logger.warning("semantic_scholar_rate_limited", query=query)
            raise SourceError(
                source_type=self.source_type,
                message="Semantic Scholar rate-limited (HTTP 429)",
                recoverable=True,
            )
        if response.status_code >= 500:
            raise SourceError(
                source_type=self.source_type,
                message=f"Semantic Scholar server error (HTTP {response.status_code})",
                recoverable=True,
            )
        if response.status_code >= 400:
            raise SourceError(
                source_type=self.source_type,
                message=f"Semantic Scholar client error (HTTP {response.status_code})",
                recoverable=False,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceError(
                source_type=self.source_type,
                message="Semantic Scholar returned non-JSON payload",
                recoverable=True,
            ) from exc

        papers: list[dict[str, Any]] = payload.get("data") or []
        results: list[SourceResult] = []
        for rank, paper in enumerate(papers[:limit]):
            relevance = max(0.1, 1.0 - rank * 0.05)
            results.append(self._paper_to_result(paper, relevance_score=relevance))
        units, unit_cost, _ = free_source_cost()
        await emit_source_cost(
            provider="semantic_scholar",
            kind="search",
            units=units,
            unit_cost_usd=unit_cost,
            latency_ms=0,
        )
        logger.debug(
            "semantic_scholar_search_complete", query=query, result_count=len(results)
        )
        return results

    async def fetch_full(
        self, url: str, *, timeout: float = 10.0
    ) -> SourceResult | None:
        paper_id = self._extract_paper_id(url)
        if not paper_id:
            return None
        try:
            t0 = time.perf_counter()
            with anyio.fail_after(timeout):
                async with self._client() as client:
                    response = await client.get(
                        f"{_BASE_URL}/paper/{paper_id}",
                        params={"fields": _SEARCH_FIELDS + ",tldr"},
                    )
            latency_ms = int((time.perf_counter() - t0) * 1000)
            units, unit_cost, _ = free_source_cost()
            await emit_source_cost(
                provider="semantic_scholar",
                kind="fetch",
                units=units,
                unit_cost_usd=unit_cost,
                latency_ms=latency_ms,
            )
        except TimeoutError:
            logger.warning(
                "semantic_scholar_fetch_full_timeout", url=url, timeout=timeout
            )
            return None
        except httpx.HTTPError as exc:
            logger.warning(
                "semantic_scholar_fetch_full_error", url=url, error=str(exc)
            )
            return None

        if response.status_code != 200:
            return None
        try:
            paper = response.json()
        except ValueError:
            return None

        result = self._paper_to_result(paper, relevance_score=1.0)
        tldr = (paper.get("tldr") or {}).get("text") if isinstance(paper.get("tldr"), dict) else None
        if tldr:
            abstract = (paper.get("abstract") or "").strip()
            merged = f"TL;DR: {tldr}\n\n{abstract}".strip()
            if len(merged) > DEFAULT_MAX_CONTENT_CHARS:
                merged = merged[:DEFAULT_MAX_CONTENT_CHARS] + "..."
            result = result.model_copy(update={"content": merged})
        return result

    @staticmethod
    def _extract_paper_id(url: str) -> str | None:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if "semanticscholar.org" not in host:
            return None
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "paper":
            return parts[-1]
        if parts:
            return parts[-1]
        return None

    async def health_check(self) -> bool:
        """Lightweight probe: fetch the canonical 'Attention Is All You Need' paper
        by its S2 paper ID instead of running a full text search.

        A direct paper lookup is one cheap request, not a paginated search query,
        which reduces the risk of triggering rate limits during health probes.
        A 429 is propagated as ``httpx.HTTPStatusError`` so the probe runner
        maps it to ``RateLimitError`` -> ``DEGRADED`` (yellow), not ``DOWN``.
        """
        url = "https://api.semanticscholar.org/graph/v1/paper/arXiv:1706.03762"
        headers = self._headers()
        if self._api_key:
            headers["x-api-key"] = self._api_key
        async with httpx.AsyncClient(timeout=1.5, headers=headers) as client:
            response = await client.get(url, params={"fields": "title"})
        if response.status_code == 429:
            response.raise_for_status()  # -> propagates as 429 to probe layer
        return response.status_code == 200

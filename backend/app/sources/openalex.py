"""OpenAlex source — open scholarly graph (https://openalex.org).

Fully free, no API key. Joining the "polite pool" by sending a
``mailto`` query param (when ``openalex_email`` is configured) gives
faster, more reliable responses.

Recency filter maps ``days`` to OpenAlex's ``from_publication_date``
filter, which supports day-level precision (unlike Semantic Scholar).

Abstracts are returned as ``abstract_inverted_index`` (word -> list of
positions). We reconstruct them into plain text on the fly.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
import httpx
import structlog

from app.config import settings
from app.domain.enums import SourceType
from app.seams.source import SourceError, SourceResult
from app.sources.base import DEFAULT_MAX_CONTENT_CHARS, BaseSource

logger = structlog.get_logger(__name__)

_BASE_URL = "https://api.openalex.org"
_SELECT_FIELDS = (
    "id,doi,title,abstract_inverted_index,publication_year,publication_date,"
    "authorships,primary_location,cited_by_count,open_access,type"
)


def _citation_bump(citation_count: int) -> float:
    """C6: log-scaled relevance bump from citation count.

    Mirrors the SemanticScholar formula so academic results from either
    source can be compared on a single relevance scale. Caps at +0.30 at
    ~1000 citations and degrades smoothly to 0 at 0 citations.
    """
    if citation_count <= 0:
        return 0.0
    return min(0.30, math.log10(1 + citation_count) / math.log10(1001) * 0.30)


class OpenAlexSource(BaseSource):
    """OpenAlex Works API client.

    Optional ``transport`` lets tests inject ``httpx.MockTransport``.
    """

    def __init__(
        self,
        *,
        email: str | None = None,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        configured_email = email if email is not None else getattr(
            settings, "openalex_email", None
        )
        self._email = (configured_email or "").strip() or None

        configured_key = api_key
        if configured_key is None:
            secret = getattr(settings, "openalex_api_key", None)
            configured_key = secret.get_secret_value() if secret is not None else None
        self._api_key = (configured_key or "").strip() or None

        self._transport = transport
        self._timeout = timeout

    @property
    def source_type(self) -> SourceType:
        return SourceType.OPENALEX

    @property
    def name(self) -> str:
        return "OpenAlex"

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": "Novum/1.0 (research agent; contact: novum@duckdns.org)"}

    def _client(self) -> httpx.AsyncClient:
        kwargs: dict[str, Any] = {"timeout": self._timeout, "headers": self._headers()}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    def _polite_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self._email:
            params["mailto"] = self._email
        if self._api_key:
            params["api_key"] = self._api_key
        return params

    @staticmethod
    def _from_date_from_days(days: int | None) -> str | None:
        if days is None or days <= 0:
            return None
        start = datetime.now(tz=UTC).date() - timedelta(days=days)
        return start.isoformat()

    @staticmethod
    def _reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str:
        if not inverted:
            return ""
        positions: dict[int, str] = {}
        for word, idxs in inverted.items():
            for i in idxs:
                positions[i] = word
        if not positions:
            return ""
        ordered = [positions[i] for i in sorted(positions)]
        return " ".join(ordered)

    def _work_to_result(
        self, work: dict[str, Any], relevance_score: float
    ) -> SourceResult:
        title = (work.get("title") or "").strip() or "(untitled)"
        abstract = self._reconstruct_abstract(
            work.get("abstract_inverted_index")
        ).strip()

        doi = work.get("doi") or ""
        if doi and not doi.startswith("http"):
            doi = f"https://doi.org/{doi}"
        openalex_id = work.get("id") or ""
        url = doi or openalex_id or ""

        published_date = work.get("publication_date")
        if not published_date and work.get("publication_year"):
            published_date = f"{work['publication_year']}-01-01"

        authors_field = work.get("authorships") or []
        author_names: list[str] = []
        for entry in authors_field[:3]:
            author = entry.get("author") if isinstance(entry, dict) else None
            name = (author or {}).get("display_name") if isinstance(author, dict) else None
            if name:
                author_names.append(name)
        authors = ", ".join(author_names)

        primary_location = work.get("primary_location") or {}
        venue_source = (
            primary_location.get("source") if isinstance(primary_location, dict) else None
        )
        venue = (
            (venue_source or {}).get("display_name", "") if isinstance(venue_source, dict) else ""
        )

        citation_count = work.get("cited_by_count") or 0
        prefix_parts = [p for p in [authors, venue, f"cited {citation_count}x"] if p]
        prefix = " — ".join(prefix_parts)
        snippet_body = abstract or title
        snippet = (f"[{prefix}] {snippet_body}" if prefix else snippet_body)[:500]

        content = abstract if abstract else None
        if content and len(content) > DEFAULT_MAX_CONTENT_CHARS:
            content = content[:DEFAULT_MAX_CONTENT_CHARS] + "..."

        # C6: citation-weighted ranking. Same log-scaled bump as
        # SemanticScholar so both academic sources are ranked on a
        # comparable scale before dedup/scoring.
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
        per_page = max(1, min(max_results, 25))
        params: dict[str, Any] = {
            "search": query,
            "per_page": per_page,
            "select": _SELECT_FIELDS,
        }
        from_date = self._from_date_from_days(days)
        if from_date is not None:
            params["filter"] = f"from_publication_date:{from_date}"
        params.update(self._polite_params())

        logger.debug(
            "openalex_search_start", query=query, per_page=per_page, from_date=from_date
        )
        try:
            async with self._client() as client:
                response = await client.get(f"{_BASE_URL}/works", params=params)
        except httpx.HTTPError as exc:
            logger.error("openalex_search_error", query=query, error=str(exc))
            raise SourceError(
                source_type=self.source_type,
                message="OpenAlex request failed",
                recoverable=True,
            ) from exc

        if response.status_code == 429:
            logger.warning("openalex_rate_limited", query=query)
            raise SourceError(
                source_type=self.source_type,
                message="OpenAlex rate-limited (HTTP 429)",
                recoverable=True,
            )
        if response.status_code >= 500:
            raise SourceError(
                source_type=self.source_type,
                message=f"OpenAlex server error (HTTP {response.status_code})",
                recoverable=True,
            )
        if response.status_code >= 400:
            raise SourceError(
                source_type=self.source_type,
                message=f"OpenAlex client error (HTTP {response.status_code})",
                recoverable=False,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceError(
                source_type=self.source_type,
                message="OpenAlex returned non-JSON payload",
                recoverable=True,
            ) from exc

        works: list[dict[str, Any]] = payload.get("results") or []
        results: list[SourceResult] = []
        for rank, work in enumerate(works[:per_page]):
            relevance = max(0.1, 1.0 - rank * 0.05)
            results.append(self._work_to_result(work, relevance_score=relevance))
        logger.debug(
            "openalex_search_complete", query=query, result_count=len(results)
        )
        return results

    async def fetch_full(
        self, url: str, *, timeout: float = 10.0
    ) -> SourceResult | None:
        work_id = self._extract_work_id(url)
        if not work_id:
            return None
        params: dict[str, Any] = {"select": _SELECT_FIELDS}
        params.update(self._polite_params())
        try:
            with anyio.fail_after(timeout):
                async with self._client() as client:
                    response = await client.get(
                        f"{_BASE_URL}/works/{work_id}", params=params
                    )
        except TimeoutError:
            logger.warning("openalex_fetch_full_timeout", url=url, timeout=timeout)
            return None
        except httpx.HTTPError as exc:
            logger.warning("openalex_fetch_full_error", url=url, error=str(exc))
            return None

        if response.status_code != 200:
            return None
        try:
            work = response.json()
        except ValueError:
            return None
        return self._work_to_result(work, relevance_score=1.0)

    async def health_check(self) -> bool:
        """Smoke check: root endpoint returns API version info with no quota cost.

        Uses a 1.5 s httpx timeout so it always resolves inside
        the probe window (``PROBE_TIMEOUT_S = 2.0 s``).
        """
        try:
            async with httpx.AsyncClient(
                timeout=1.5, headers=self._headers()
            ) as client:
                response = await client.get(_BASE_URL)
            return response.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _extract_work_id(url: str) -> str | None:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path or ""
        if "openalex.org" in host:
            parts = [p for p in path.split("/") if p]
            if parts:
                last = parts[-1]
                if last.lower().startswith("w") and last[1:].isdigit():
                    return last
                return last
            return None
        if "doi.org" in host:
            doi = path.lstrip("/")
            if doi:
                return f"doi:{doi}"
        return None

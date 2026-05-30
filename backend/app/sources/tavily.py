"""Tavily web search source (V1)."""

from __future__ import annotations

import time
from typing import Any

import structlog
from tavily import AsyncTavilyClient

from app.config import settings
from app.domain.enums import SourceType
from app.seams.source import SourceError, SourceResult
from app.sources._cost import emit_source_cost
from app.sources.base import BaseSource
from app.sources.pricing import tavily_cost

logger = structlog.get_logger(__name__)

# Domains that the AuthorityTier classifier marks LOW_SIGNAL (×0.70 on
# coverage/diversity). Excluding them at the query level — instead of
# down-weighting after the fact — frees up slots of ``max_results`` for
# higher-tier content. Mirrors ``app.agent.sources_authority.tiers``.
_DEFAULT_EXCLUDE_DOMAINS: tuple[str, ...] = (
    "medium.com",
    "quora.com",
    "answers.com",
    "geeksforgeeks.org",
    "w3schools.com",
    "tutorialspoint.com",
    "javatpoint.com",
    "blogspot.com",
    "wordpress.com",
    "substack.com",
)


class TavilySource(BaseSource):
    """Tavily web search implementation."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key if api_key is not None else settings.tavily_api_key
        self._client = AsyncTavilyClient(api_key=key)

    @property
    def source_type(self) -> SourceType:
        return SourceType.TAVILY

    @property
    def name(self) -> str:
        return "Tavily Web Search"

    async def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        days: int | None = None,
        topic: str | None = None,
        **hints: Any,
    ) -> list[SourceResult]:
        """Search the web using Tavily's advanced search depth.

        BRD-23 WP-1: optional ``days`` recency filter forwarded to Tavily.
        ``topic`` accepts ``"news"`` (paid tier) for temporal queries or
        ``"general"`` (default). Pass ``None`` to omit the parameter.
        Paid tier raises max_results ceiling to 20.

        ``hints`` recognised:
        - ``include_domains: list[str]`` — restrict results to these
          hosts (e.g. authoritative tier).
        - ``exclude_domains: list[str]`` — appended to the always-on
          LOW_SIGNAL blocklist.
        """
        include_domains = hints.get("include_domains") or []
        extra_excludes = hints.get("exclude_domains") or []
        exclude_domains = list(_DEFAULT_EXCLUDE_DOMAINS) + [
            d for d in extra_excludes if d not in _DEFAULT_EXCLUDE_DOMAINS
        ]
        logger.debug(
            "tavily_search_start",
            query=query,
            max_results=max_results,
            days=days,
            topic=topic,
            include_domains=include_domains,
            exclude_count=len(exclude_domains),
        )
        try:
            kwargs: dict[str, Any] = dict(
                query=query,
                max_results=max(1, min(max_results, 20)),
                include_answer=False,
                include_raw_content=True,
                search_depth="advanced",
                exclude_domains=exclude_domains,
            )
            if include_domains:
                kwargs["include_domains"] = list(include_domains)
            if days is not None:
                kwargs["days"] = days
            if topic is not None:
                kwargs["topic"] = topic
            t0 = time.perf_counter()
            response: dict[str, Any] = await self._client.search(**kwargs)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            units, unit_cost, _ = tavily_cost("advanced")
            await emit_source_cost(
                provider="tavily",
                kind="search",
                units=units,
                unit_cost_usd=unit_cost,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            logger.error("tavily_search_error", query=query, error=str(exc))
            raise SourceError(
                source_type=self.source_type,
                message="Tavily search failed",
                recoverable=True,
            ) from exc

        results: list[SourceResult] = []
        for item in response.get("results", []) or []:
            raw = item.get("raw_content") or item.get("content") or ""
            snippet = (item.get("content") or "")[:500]
            results.append(
                SourceResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=snippet,
                    content=self._truncate_content(raw) if raw else None,
                    relevance_score=item.get("score"),
                    published_date=item.get("published_date"),
                )
            )

        logger.debug("tavily_search_complete", query=query, result_count=len(results))
        return results

    async def health_check(self) -> bool:
        """Smoke check: a 1-result query verifies the API key.

        Not a liveness probe — do not call on hot paths.
        """
        try:
            await self._client.search(query="health", max_results=1, search_depth="basic")
            return True
        except Exception:
            return False

    async def fetch_full(
        self, url: str, *, timeout: float = 10.0
    ) -> SourceResult | None:
        """Deep-fetch full page content via Tavily extract (BRD-23 WP-2).

        Returns ``None`` on timeout, error, or empty extraction. Content is
        capped at ``DEFAULT_MAX_CONTENT_CHARS * 4`` (~20 000 chars) to stay
        within token budgets when re-fed to the judge.
        """
        import anyio

        from app.sources.base import DEFAULT_MAX_CONTENT_CHARS

        try:
            t0 = time.perf_counter()
            with anyio.fail_after(timeout):
                response: dict[str, Any] = await self._client.extract(urls=[url])
            latency_ms = int((time.perf_counter() - t0) * 1000)
            units, unit_cost, _ = tavily_cost("advanced")
            await emit_source_cost(
                provider="tavily",
                kind="fetch",
                units=units,
                unit_cost_usd=unit_cost,
                latency_ms=latency_ms,
            )
        except TimeoutError:
            logger.warning("tavily_fetch_full_timeout", url=url, timeout=timeout)
            return None
        except Exception as exc:
            logger.warning("tavily_fetch_full_error", url=url, error=str(exc))
            return None

        results = response.get("results") or []
        if not results:
            return None
        item = results[0]
        raw = item.get("raw_content") or item.get("content") or ""
        if not raw:
            return None
        max_chars = DEFAULT_MAX_CONTENT_CHARS * 4
        content = raw if len(raw) <= max_chars else raw[:max_chars] + "..."
        return SourceResult(
            url=item.get("url", url),
            title=item.get("title", ""),
            snippet=content[:500],
            content=content,
            relevance_score=None,
            published_date=item.get("published_date"),
        )

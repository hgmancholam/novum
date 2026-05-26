"""Tavily web search source (V1)."""

from __future__ import annotations

from typing import Any

import structlog
from tavily import AsyncTavilyClient

from app.config import settings
from app.domain.enums import SourceType
from app.seams.source import SourceError, SourceResult
from app.sources.base import BaseSource

logger = structlog.get_logger(__name__)


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

    async def search(self, query: str, max_results: int = 5) -> list[SourceResult]:
        """Search the web using Tavily's advanced search depth."""
        logger.debug("tavily_search_start", query=query, max_results=max_results)
        try:
            response: dict[str, Any] = await self._client.search(
                query=query,
                max_results=max(1, min(max_results, 10)),
                include_answer=False,
                include_raw_content=True,
                search_depth="advanced",
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

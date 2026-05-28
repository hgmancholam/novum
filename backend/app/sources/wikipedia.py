"""Wikipedia source (V1).

Uses the synchronous ``wikipediaapi`` package wrapped with
``anyio.to_thread.run_sync`` so we never block the event loop.
"""

from __future__ import annotations

import anyio
import structlog
import wikipediaapi

from app.domain.enums import SourceType
from app.seams.source import SourceError, SourceResult
from app.sources.base import BaseSource

logger = structlog.get_logger(__name__)


class WikipediaSource(BaseSource):
    """Wikipedia article search and content extraction."""

    def __init__(self, language: str = "en") -> None:
        self._wiki = wikipediaapi.Wikipedia(
            user_agent="Novum/1.0 (research agent; contact: novum@duckdns.org)",
            language=language,
        )
        self._language = language

    @property
    def source_type(self) -> SourceType:
        return SourceType.WIKIPEDIA

    @property
    def name(self) -> str:
        return f"Wikipedia ({self._language})"

    async def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        days: int | None = None,  # BRD-23 WP-1: accepted for signature parity; Wikipedia ignores recency.
    ) -> list[SourceResult]:
        """Look up the article whose title matches ``query``.

        If the direct lookup misses, try a small set of title variations.
        """
        logger.debug("wikipedia_search_start", query=query, max_results=max_results)
        try:
            page = await anyio.to_thread.run_sync(self._wiki.page, query)
            if not page.exists():
                results = await self._search_suggestions(query, max_results)
            else:
                results = [self._page_to_result(page, relevance_score=1.0)]
                if max_results > 1:
                    links = list(page.links.keys())[: max_results - 1]
                    for link_title in links:
                        linked = await anyio.to_thread.run_sync(self._wiki.page, link_title)
                        if linked.exists():
                            results.append(self._page_to_result(linked, relevance_score=0.8))
        except SourceError:
            raise
        except Exception as exc:
            logger.error("wikipedia_search_error", query=query, error=str(exc))
            raise SourceError(
                source_type=self.source_type,
                message="Wikipedia search failed",
                recoverable=True,
            ) from exc

        logger.debug("wikipedia_search_complete", query=query, result_count=len(results))
        return results[:max_results]

    async def _search_suggestions(self, query: str, max_results: int) -> list[SourceResult]:
        variations = [query, query.replace("_", " "), query.replace(" ", "_")]
        seen: set[str] = set()
        results: list[SourceResult] = []
        for variation in variations:
            if len(results) >= max_results:
                break
            page = await anyio.to_thread.run_sync(self._wiki.page, variation)
            if page.exists() and page.fullurl not in seen:
                seen.add(page.fullurl)
                results.append(self._page_to_result(page, relevance_score=0.7))
        return results

    def _page_to_result(
        self, page: wikipediaapi.WikipediaPage, relevance_score: float
    ) -> SourceResult:
        summary = page.summary or ""
        text = page.text or ""
        return SourceResult(
            url=page.fullurl,
            title=page.title,
            snippet=summary[:500],
            content=self._truncate_content(text) if text else None,
            relevance_score=relevance_score,
        )

    async def health_check(self) -> bool:
        """Check that Wikipedia returns a known page."""
        try:
            page = await anyio.to_thread.run_sync(
                self._wiki.page, "Python (programming language)"
            )
            return page.exists()
        except Exception:
            return False

    async def fetch_full(
        self, url: str, *, timeout: float = 10.0
    ) -> SourceResult | None:
        """Deep-fetch the full Wikipedia article body (BRD-23 WP-2).

        The ``url`` is the Wikipedia ``fullurl``; we derive the title from
        the trailing path segment, look up the page, and return the
        article ``text`` truncated to ``DEFAULT_MAX_CONTENT_CHARS * 4``
        characters.
        """
        from urllib.parse import unquote, urlparse

        from app.sources.base import DEFAULT_MAX_CONTENT_CHARS

        title = unquote(urlparse(url).path.rsplit("/", 1)[-1]).replace("_", " ")
        if not title:
            return None

        try:
            with anyio.fail_after(timeout):
                page = await anyio.to_thread.run_sync(self._wiki.page, title)
        except TimeoutError:
            logger.warning("wikipedia_fetch_full_timeout", url=url, timeout=timeout)
            return None
        except Exception as exc:
            logger.warning("wikipedia_fetch_full_error", url=url, error=str(exc))
            return None

        if not page.exists():
            return None
        text = page.text or ""
        if not text:
            return None
        max_chars = DEFAULT_MAX_CONTENT_CHARS * 4
        content = text if len(text) <= max_chars else text[:max_chars] + "..."
        return SourceResult(
            url=page.fullurl,
            title=page.title,
            snippet=(page.summary or content)[:500],
            content=content,
            relevance_score=None,
        )

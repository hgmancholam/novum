"""Wikipedia source — MediaWiki Action API client over httpx.

Replaces the previous ``wikipediaapi`` title-lookup approach (which only
worked when the query matched a page title verbatim) with a real
full-text search using ``list=search`` and clean lead extracts using
``prop=extracts``.

The language is dynamic: instance default is ``en``, but each call can
pass ``language=`` in ``hints`` so a Spanish question hits
``es.wikipedia.org`` instead.

Disambiguation pages (detected via ``pageprops.disambiguation``) are
filtered out — they are not evidence.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import anyio
import httpx
import structlog

from app.domain.enums import SourceType
from app.seams.source import SourceError, SourceResult
from app.sources._cost import emit_source_cost
from app.sources.base import DEFAULT_MAX_CONTENT_CHARS, BaseSource
from app.sources.pricing import wikipedia_cost

logger = structlog.get_logger(__name__)

_USER_AGENT = "Novum/1.0 (research agent; contact: novum@duckdns.org)"
_SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"en", "es", "fr", "de", "pt", "it"})


def _api_url(language: str) -> str:
    lang = language if language in _SUPPORTED_LANGUAGES else "en"
    return f"https://{lang}.wikipedia.org/w/api.php"


def _wiki_page_url(language: str, title: str) -> str:
    lang = language if language in _SUPPORTED_LANGUAGES else "en"
    return f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"


class WikipediaSource(BaseSource):
    """Wikipedia search and content extraction via the MediaWiki API.

    Optional ``transport`` lets tests inject ``httpx.MockTransport``.
    """

    def __init__(
        self,
        language: str = "en",
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._language = language if language in _SUPPORTED_LANGUAGES else "en"
        self._transport = transport
        self._timeout = timeout

    @property
    def source_type(self) -> SourceType:
        return SourceType.WIKIPEDIA

    @property
    def name(self) -> str:
        return f"Wikipedia ({self._language})"

    def _client(self) -> httpx.AsyncClient:
        kwargs: dict[str, Any] = {
            "timeout": self._timeout,
            "headers": {"User-Agent": _USER_AGENT},
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    def _resolve_language(self, hints_language: object) -> str:
        if isinstance(hints_language, str) and hints_language in _SUPPORTED_LANGUAGES:
            return hints_language
        return self._language

    async def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        days: int | None = None,  # Accepted for signature parity; Wikipedia ignores recency.
        **hints: Any,
    ) -> list[SourceResult]:
        """Full-text search via ``action=query&list=search`` then ``prop=extracts``."""
        language = self._resolve_language(hints.get("language"))
        srlimit = max(1, min(max_results, 10))
        api = _api_url(language)
        logger.debug(
            "wikipedia_search_start",
            query=query,
            max_results=max_results,
            language=language,
        )
        t0 = time.perf_counter()
        try:
            async with self._client() as client:
                titles = await self._search_titles(client, api, query, srlimit)
                if not titles:
                    results: list[SourceResult] = []
                else:
                    results = await self._fetch_extracts(client, api, language, titles)
        except httpx.HTTPError as exc:
            logger.error("wikipedia_search_error", query=query, error=str(exc))
            raise SourceError(
                source_type=self.source_type,
                message="Wikipedia request failed",
                recoverable=True,
            ) from exc
        latency_ms = int((time.perf_counter() - t0) * 1000)
        units, unit_cost, _ = wikipedia_cost()
        await emit_source_cost(
            provider="wikipedia",
            kind="search",
            units=units,
            unit_cost_usd=unit_cost,
            latency_ms=latency_ms,
        )
        logger.debug(
            "wikipedia_search_complete",
            query=query,
            result_count=len(results),
            language=language,
        )
        return results[:max_results]

    async def _search_titles(
        self,
        client: httpx.AsyncClient,
        api: str,
        query: str,
        srlimit: int,
    ) -> list[str]:
        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": str(srlimit),
            "srprop": "snippet",
        }
        response = await client.get(api, params=params)
        if response.status_code >= 500:
            raise SourceError(
                source_type=self.source_type,
                message=f"Wikipedia server error (HTTP {response.status_code})",
                recoverable=True,
            )
        if response.status_code >= 400:
            raise SourceError(
                source_type=self.source_type,
                message=f"Wikipedia client error (HTTP {response.status_code})",
                recoverable=False,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceError(
                source_type=self.source_type,
                message="Wikipedia returned non-JSON payload",
                recoverable=True,
            ) from exc
        hits = (payload.get("query") or {}).get("search") or []
        return [str(h.get("title", "")) for h in hits if h.get("title")]

    async def _fetch_extracts(
        self,
        client: httpx.AsyncClient,
        api: str,
        language: str,
        titles: list[str],
    ) -> list[SourceResult]:
        # One round-trip for the top titles: lead extract + URL +
        # disambiguation flag. Order is preserved by sorting the response
        # pages back into the input ``titles`` order.
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts|info|pageprops",
            "exintro": "1",
            "explaintext": "1",
            "exsentences": "5",
            "inprop": "url",
            "ppprop": "disambiguation",
            "titles": "|".join(titles),
            "redirects": "1",
        }
        response = await client.get(api, params=params)
        if response.status_code >= 500:
            raise SourceError(
                source_type=self.source_type,
                message=f"Wikipedia server error (HTTP {response.status_code})",
                recoverable=True,
            )
        if response.status_code >= 400:
            raise SourceError(
                source_type=self.source_type,
                message=f"Wikipedia client error (HTTP {response.status_code})",
                recoverable=False,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceError(
                source_type=self.source_type,
                message="Wikipedia returned non-JSON payload",
                recoverable=True,
            ) from exc

        pages_dict: dict[str, dict[str, Any]] = (
            (payload.get("query") or {}).get("pages") or {}
        )
        pages = list(pages_dict.values())
        # Honour the search ranking from ``list=search``: index pages by
        # normalised title, then walk ``titles`` in order.
        by_title: dict[str, dict[str, Any]] = {}
        for page in pages:
            title = page.get("title")
            if isinstance(title, str):
                by_title[title.lower()] = page

        results: list[SourceResult] = []
        for rank, title in enumerate(titles):
            page = by_title.get(title.lower())
            if not page:
                continue
            if "missing" in page:
                continue
            # Skip disambiguation pages: not evidence, would mislead the judge.
            pageprops = page.get("pageprops") or {}
            if isinstance(pageprops, dict) and "disambiguation" in pageprops:
                continue
            extract = (page.get("extract") or "").strip()
            if not extract:
                continue
            url = page.get("fullurl") or _wiki_page_url(language, str(page.get("title", title)))
            relevance = max(0.1, 1.0 - rank * 0.1)
            content = extract if len(extract) <= DEFAULT_MAX_CONTENT_CHARS else extract[:DEFAULT_MAX_CONTENT_CHARS] + "..."
            results.append(
                SourceResult(
                    url=str(url),
                    title=str(page.get("title", title)),
                    snippet=extract[:500],
                    content=content,
                    relevance_score=relevance,
                )
            )
        return results

    async def health_check(self) -> bool:
        """Smoke check: a 1-result search on the configured language."""
        try:
            api = _api_url(self._language)
            async with self._client() as client:
                response = await client.get(
                    api,
                    params={
                        "action": "query",
                        "format": "json",
                        "list": "search",
                        "srsearch": "Python",
                        "srlimit": "1",
                    },
                )
            return response.status_code == 200
        except Exception:
            return False

    async def fetch_full(
        self, url: str, *, timeout: float = 10.0
    ) -> SourceResult | None:
        """Deep-fetch the full Wikipedia article body via ``prop=extracts``.

        Derives ``(language, title)`` from the URL host + path; falls back
        to the instance default language when the host is unrecognised.
        """
        from urllib.parse import unquote, urlparse

        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        language = self._language
        for candidate in _SUPPORTED_LANGUAGES:
            if host == f"{candidate}.wikipedia.org":
                language = candidate
                break
        title = unquote(parsed.path.rsplit("/", 1)[-1]).replace("_", " ")
        if not title:
            return None

        api = _api_url(language)
        try:
            t0 = time.perf_counter()
            with anyio.fail_after(timeout):
                async with self._client() as client:
                    response = await client.get(
                        api,
                        params={
                            "action": "query",
                            "format": "json",
                            "prop": "extracts|info",
                            "explaintext": "1",
                            "inprop": "url",
                            "titles": title,
                            "redirects": "1",
                        },
                    )
            latency_ms = int((time.perf_counter() - t0) * 1000)
            units, unit_cost, _ = wikipedia_cost()
            await emit_source_cost(
                provider="wikipedia",
                kind="fetch",
                units=units,
                unit_cost_usd=unit_cost,
                latency_ms=latency_ms,
            )
        except TimeoutError:
            logger.warning("wikipedia_fetch_full_timeout", url=url, timeout=timeout)
            return None
        except Exception as exc:
            logger.warning("wikipedia_fetch_full_error", url=url, error=str(exc))
            return None

        if response.status_code != 200:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        pages = list(((payload.get("query") or {}).get("pages") or {}).values())
        if not pages:
            return None
        page = pages[0]
        if "missing" in page:
            return None
        extract = (page.get("extract") or "").strip()
        if not extract:
            return None
        max_chars = DEFAULT_MAX_CONTENT_CHARS * 4
        content = extract if len(extract) <= max_chars else extract[:max_chars] + "..."
        return SourceResult(
            url=str(page.get("fullurl") or _wiki_page_url(language, str(page.get("title", title)))),
            title=str(page.get("title", title)),
            snippet=content[:500],
            content=content,
            relevance_score=None,
        )


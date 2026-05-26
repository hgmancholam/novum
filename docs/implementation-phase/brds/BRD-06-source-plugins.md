# BRD-06: Source Plugins (Tavily + Wikipedia)

**Document ID:** BRD-06
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 7 of 19

---

## 1. Executive Summary

Implement the Source plugin seam with two V1 implementations: Tavily (web search) and Wikipedia. This establishes the extensible plugin pattern for adding new sources in V2 (Confluence, arXiv, SQL).

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-15 | Source diversity/independence | Complete |
| — | Plugin seam architecture | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-00, BRD-02 | BRD-07 |

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    seams/
      __init__.py
      source.py             # Source protocol definition
    sources/
      __init__.py
      base.py               # Base source class
      tavily.py             # Tavily implementation
      wikipedia.py          # Wikipedia implementation
      registry.py           # Source registry
```

### 4.2 Source Protocol

#### backend/app/seams/source.py

```python
"""Source plugin seam — one of three extensibility points.

Sources provide evidence for research claims.
V1: Tavily (web search), Wikipedia
V2: Confluence, arXiv, SQL, custom
"""

from abc import abstractmethod
from typing import Protocol, runtime_checkable

from app.domain.enums import SourceType


class SourceResult:
    """A single result from a source search."""

    def __init__(
        self,
        url: str,
        title: str,
        snippet: str,
        content: str | None = None,
        relevance_score: float | None = None,
        published_date: str | None = None,
    ) -> None:
        self.url = url
        self.title = title
        self.snippet = snippet
        self.content = content
        self.relevance_score = relevance_score
        self.published_date = published_date

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "content": self.content,
            "relevance_score": self.relevance_score,
            "published_date": self.published_date,
        }


class SourceError(Exception):
    """Base exception for source errors."""

    def __init__(self, source_type: SourceType, message: str, recoverable: bool = True) -> None:
        self.source_type = source_type
        self.message = message
        self.recoverable = recoverable
        super().__init__(message)


@runtime_checkable
class Source(Protocol):
    """Protocol for source plugins.
    
    Implement this protocol to add new sources.
    """

    @property
    def source_type(self) -> SourceType:
        """Return the source type identifier."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name for the source."""
        ...

    async def search(self, query: str, max_results: int = 5) -> list[SourceResult]:
        """Search the source for information.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of SourceResult objects
            
        Raises:
            SourceError: If the search fails
        """
        ...

    async def health_check(self) -> bool:
        """Check if the source is available.
        
        Returns True if healthy, False otherwise.
        """
        ...
```

### 4.3 Base Source Class

#### backend/app/sources/base.py

```python
"""Base source implementation with common functionality."""

from abc import ABC, abstractmethod

from app.domain.enums import SourceType
from app.seams.source import Source, SourceResult, SourceError


class BaseSource(ABC):
    """Abstract base class for source implementations."""

    @property
    @abstractmethod
    def source_type(self) -> SourceType:
        """Return the source type identifier."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name."""
        pass

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> list[SourceResult]:
        """Execute search."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check health."""
        pass

    def _truncate_content(self, content: str, max_chars: int = 5000) -> str:
        """Truncate content to max characters."""
        if len(content) <= max_chars:
            return content
        return content[:max_chars] + "..."
```

### 4.4 Tavily Implementation

#### backend/app/sources/tavily.py

```python
"""Tavily web search source implementation.

Tavily provides AI-optimized web search results with content extraction.
Free tier: 1000 searches/month.
"""

from tavily import AsyncTavilyClient
import structlog

from app.config import settings
from app.domain.enums import SourceType
from app.seams.source import SourceResult, SourceError
from app.sources.base import BaseSource

logger = structlog.get_logger()


class TavilySource(BaseSource):
    """Tavily web search implementation."""

    def __init__(self) -> None:
        self._client = AsyncTavilyClient(api_key=settings.tavily_api_key)

    @property
    def source_type(self) -> SourceType:
        return SourceType.TAVILY

    @property
    def name(self) -> str:
        return "Tavily Web Search"

    async def search(self, query: str, max_results: int = 5) -> list[SourceResult]:
        """Search the web using Tavily API.
        
        Args:
            query: Search query
            max_results: Max results (1-10)
            
        Returns:
            List of SourceResult with content extracted
        """
        logger.debug("tavily_search_start", query=query, max_results=max_results)

        try:
            response = await self._client.search(
                query=query,
                max_results=min(max_results, 10),
                include_answer=False,  # We generate our own answer
                include_raw_content=True,
                search_depth="advanced",
            )
        except Exception as e:
            logger.error("tavily_search_error", query=query, error=str(e))
            raise SourceError(
                source_type=self.source_type,
                message=f"Tavily search failed: {str(e)}",
                recoverable=True,
            )

        results = []
        for item in response.get("results", []):
            results.append(
                SourceResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("content", "")[:500],
                    content=self._truncate_content(item.get("raw_content", item.get("content", ""))),
                    relevance_score=item.get("score"),
                    published_date=item.get("published_date"),
                )
            )

        logger.debug("tavily_search_complete", query=query, result_count=len(results))
        return results

    async def health_check(self) -> bool:
        """Check if Tavily API is reachable."""
        try:
            # Light search to verify API key
            await self._client.search(query="test", max_results=1)
            return True
        except Exception:
            return False
```

### 4.5 Wikipedia Implementation

#### backend/app/sources/wikipedia.py

```python
"""Wikipedia source implementation.

Uses wikipedia-api package for article search and content extraction.
Free tier: Unlimited (no API key required).
"""

import wikipediaapi
import structlog

from app.domain.enums import SourceType
from app.seams.source import SourceResult, SourceError
from app.sources.base import BaseSource

logger = structlog.get_logger()


class WikipediaSource(BaseSource):
    """Wikipedia search and content extraction."""

    def __init__(self, language: str = "en") -> None:
        self._wiki = wikipediaapi.Wikipedia(
            user_agent="Novum/1.0 (research agent)",
            language=language,
        )
        self._language = language

    @property
    def source_type(self) -> SourceType:
        return SourceType.WIKIPEDIA

    @property
    def name(self) -> str:
        return f"Wikipedia ({self._language})"

    async def search(self, query: str, max_results: int = 5) -> list[SourceResult]:
        """Search Wikipedia for articles.
        
        Uses page search and extracts summaries.
        """
        logger.debug("wikipedia_search_start", query=query, max_results=max_results)

        try:
            # Wikipedia-api doesn't have async, but it's I/O-light
            # For V1, we run it sync. For V2, consider anyio.to_thread
            page = self._wiki.page(query)

            if not page.exists():
                # Try search suggestions
                return await self._search_suggestions(query, max_results)

            results = [
                SourceResult(
                    url=page.fullurl,
                    title=page.title,
                    snippet=page.summary[:500] if page.summary else "",
                    content=self._truncate_content(page.text) if page.text else None,
                    relevance_score=1.0,  # Direct match
                )
            ]

            # Add linked pages for more results
            if max_results > 1:
                for link_title in list(page.links.keys())[:max_results - 1]:
                    linked_page = self._wiki.page(link_title)
                    if linked_page.exists():
                        results.append(
                            SourceResult(
                                url=linked_page.fullurl,
                                title=linked_page.title,
                                snippet=linked_page.summary[:500] if linked_page.summary else "",
                                content=self._truncate_content(linked_page.text) if linked_page.text else None,
                                relevance_score=0.8,
                            )
                        )

            logger.debug("wikipedia_search_complete", query=query, result_count=len(results))
            return results[:max_results]

        except Exception as e:
            logger.error("wikipedia_search_error", query=query, error=str(e))
            raise SourceError(
                source_type=self.source_type,
                message=f"Wikipedia search failed: {str(e)}",
                recoverable=True,
            )

    async def _search_suggestions(self, query: str, max_results: int) -> list[SourceResult]:
        """Fallback: search using page title variations."""
        results = []
        
        # Try common variations
        variations = [
            query,
            query.title(),
            query.lower(),
            query.replace(" ", "_"),
        ]

        seen_urls = set()
        for variation in variations:
            if len(results) >= max_results:
                break
                
            page = self._wiki.page(variation)
            if page.exists() and page.fullurl not in seen_urls:
                seen_urls.add(page.fullurl)
                results.append(
                    SourceResult(
                        url=page.fullurl,
                        title=page.title,
                        snippet=page.summary[:500] if page.summary else "",
                        content=self._truncate_content(page.text) if page.text else None,
                        relevance_score=0.7,
                    )
                )

        return results

    async def health_check(self) -> bool:
        """Check if Wikipedia is reachable."""
        try:
            page = self._wiki.page("Python (programming language)")
            return page.exists()
        except Exception:
            return False
```

### 4.6 Source Registry

#### backend/app/sources/registry.py

```python
"""Source registry for managing available sources."""

from typing import Dict

from app.domain.enums import SourceType
from app.seams.source import Source
from app.sources.tavily import TavilySource
from app.sources.wikipedia import WikipediaSource


class SourceRegistry:
    """Registry of available source plugins."""

    _sources: Dict[SourceType, Source] = {}
    _initialized: bool = False

    @classmethod
    def initialize(cls) -> None:
        """Initialize all sources."""
        if cls._initialized:
            return

        cls._sources = {
            SourceType.TAVILY: TavilySource(),
            SourceType.WIKIPEDIA: WikipediaSource(),
        }
        cls._initialized = True

    @classmethod
    def get(cls, source_type: SourceType) -> Source:
        """Get a source by type."""
        if not cls._initialized:
            cls.initialize()
        
        if source_type not in cls._sources:
            raise ValueError(f"Unknown source type: {source_type}")
        
        return cls._sources[source_type]

    @classmethod
    def all(cls) -> list[Source]:
        """Get all registered sources."""
        if not cls._initialized:
            cls.initialize()
        return list(cls._sources.values())

    @classmethod
    def types(cls) -> list[SourceType]:
        """Get all registered source types."""
        if not cls._initialized:
            cls.initialize()
        return list(cls._sources.keys())


# Convenience function
def get_source(source_type: SourceType) -> Source:
    """Get a source by type."""
    return SourceRegistry.get(source_type)
```

### 4.7 Package Exports

#### backend/app/sources/__init__.py

```python
"""Source plugins package."""

from app.sources.registry import SourceRegistry, get_source
from app.sources.tavily import TavilySource
from app.sources.wikipedia import WikipediaSource

__all__ = [
    "SourceRegistry",
    "get_source",
    "TavilySource",
    "WikipediaSource",
]
```

#### backend/app/seams/__init__.py

```python
"""Plugin seams package.

Three extensibility points:
1. Source — data retrieval (this file)
2. StoppingSignal — when to stop (BRD-09)
3. OutputRenderer — answer formatting (BRD-16)
"""

from app.seams.source import Source, SourceResult, SourceError

__all__ = ["Source", "SourceResult", "SourceError"]
```

---

## 5. Acceptance Criteria

### AC-01: Tavily Search Returns Results
```gherkin
Given valid TAVILY_API_KEY
When I call TavilySource().search("Python programming", max_results=3)
Then a list of 1-3 SourceResult is returned
  And each result has url, title, snippet, and content
```

### AC-02: Wikipedia Search Returns Results
```gherkin
Given Wikipedia is accessible
When I call WikipediaSource().search("Albert Einstein")
Then a list of SourceResult is returned
  And the first result is the Einstein article
  And content contains extracted text
```

### AC-03: Source Registry Provides All Sources
```gherkin
Given the registry is initialized
When I call SourceRegistry.all()
Then 2 sources are returned (Tavily, Wikipedia)
When I call get_source(SourceType.TAVILY)
Then a TavilySource instance is returned
```

### AC-04: Source Errors Are Catchable
```gherkin
Given invalid API key for Tavily
When I call TavilySource().search("test")
Then a SourceError is raised
  And error.source_type equals SourceType.TAVILY
  And error.recoverable is True
```

### AC-05: Health Check Works
```gherkin
Given valid credentials
When I call source.health_check() for each source
Then all return True
When credentials are invalid
Then Tavily returns False
```

---

## 6. Implementation Checklist

- [ ] Create `backend/app/seams/__init__.py`
- [ ] Create `backend/app/seams/source.py`
- [ ] Create `backend/app/sources/__init__.py`
- [ ] Create `backend/app/sources/base.py`
- [ ] Create `backend/app/sources/tavily.py`
- [ ] Create `backend/app/sources/wikipedia.py`
- [ ] Create `backend/app/sources/registry.py`
- [ ] Write unit tests with mocked APIs
- [ ] Write integration tests (manual, uses real APIs)
- [ ] Verify source diversity for RF-15

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | pytest + pytest-httpx | Mocked API responses | 100% |
| Integration | pytest | Real API (manual) | Smoke test |
| Protocol | pytest | Source protocol compliance | 100% |

## 8. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TAVILY_API_KEY` | Yes | — | Tavily API key |

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Tavily rate limit (1000/mo) | Med | Med | Track usage, cache results |
| Wikipedia blocking | Low | Low | User-agent includes contact |
| Source content too long | Med | High | Truncation at 5000 chars |
| No results for query | Med | Med | Fallback between sources |

## 10. Out of Scope

- Result caching (V2)
- Source priority/weighting
- Additional sources (Confluence, arXiv, SQL)
- Async Wikipedia client
- Source quality scoring

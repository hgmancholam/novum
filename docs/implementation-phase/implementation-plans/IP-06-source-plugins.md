# Implementation Plan: BRD-06 Source Plugins (Tavily + Wikipedia)

**Plan ID:** IP-06
**BRD Reference:** [BRD-06-source-plugins.md](../brds/BRD-06-source-plugins.md)
**Created:** 2026-05-26
**Status:** Ready for Coder
**Implementation Order:** 7 of 19

---

## 1. Overview

Implement the **Source** plugin seam — the first of the three V1 extensibility points (architecture rule #1) — with two concrete sources: **Tavily** (web search) and **Wikipedia**. The seam lives under [backend/app/seams/](../../../backend/app/seams/) and the concrete plugins under [backend/app/sources/](../../../backend/app/sources/). A `SourceRegistry` exposes both as a typed registry keyed by `SourceType` (the enum already exists in [backend/app/domain/enums.py](../../../backend/app/domain/enums.py)).

**Non-goals (deferred):**
- Wiring sources into the FSM / planner (BRD-07).
- Source cascade / fallback logic on `SourceFailed` (BRD-07 + BRD-09).
- Caching, rate-limit accounting, vector indexing (V2).
- New source types beyond Tavily/Wikipedia (V2).
- Persisting `EvidenceAdded` events from search results (BRD-07/08).

---

## 2. Architectural Alignment

| Rule (copilot-instructions §3) | Compliance |
|---|---|
| #1 Three plugin seams | `Source` is implemented as a `runtime_checkable` `Protocol` in `app/seams/source.py`. |
| #2 Storage/planner/LLM are **not** seams | Sources do not import from `app/llm/` or `app/services/`. |
| #4 Append-only events | Out of scope — sources are pure search; emitting `SourceFailed`/`EvidenceAdded` is the FSM's job (BRD-07). |
| English-only artifacts (L-001) | All code, logs, exceptions in English. |
| `pyright --strict` + `ruff` clean | Explicit type annotations everywhere; no `Any`; no `dict` without parameters; `from __future__ import annotations`. |
| Async-first (copilot-instructions §4) | `Source.search` and `Source.health_check` are `async`. Wikipedia (sync client) is dispatched via `anyio.to_thread.run_sync`. |
| Retries via `tenacity` | **Not** used here — Tavily client has its own retries, Wikipedia is best-effort. Add retries only if BRD-07 needs them. |

**Pre-existing state (verified):**
- [backend/app/seams/__init__.py](../../../backend/app/seams/__init__.py) exists, empty.
- [backend/app/sources/__init__.py](../../../backend/app/sources/__init__.py) exists, empty.
- `SourceType.TAVILY` and `SourceType.WIKIPEDIA` exist in [backend/app/domain/enums.py](../../../backend/app/domain/enums.py).
- `tavily-python>=0.5.0` and `wikipedia-api>=0.7.0` are pinned in [backend/pyproject.toml](../../../backend/pyproject.toml).
- `settings.tavily_api_key` exists in [backend/app/config.py](../../../backend/app/config.py).
- `structlog` is the project logger; `anyio` is already a dependency.

---

## 3. File Layout

Create (or replace empty `__init__.py`):

```
backend/app/seams/
  __init__.py          # re-export Source, SourceResult, SourceError
  source.py            # Protocol + SourceResult + SourceError

backend/app/sources/
  __init__.py          # re-export TavilySource, WikipediaSource, SourceRegistry, get_source
  base.py              # BaseSource ABC + content truncation helper
  tavily.py            # TavilySource
  wikipedia.py         # WikipediaSource (sync client wrapped with anyio.to_thread)
  registry.py          # SourceRegistry + module-level get_source helper

backend/tests/
  test_seams_source.py     # Protocol + SourceResult + SourceError
  test_sources_base.py     # truncation helper
  test_sources_tavily.py   # TavilySource (AsyncMock'd tavily client)
  test_sources_wikipedia.py # WikipediaSource (monkeypatched wikipediaapi)
  test_sources_registry.py # SourceRegistry
```

No other directory is touched.

---

## 4. Deviations from BRD-06 §4 (binding overrides)

BRD-06 §4 is the structural reference but contains issues that must be corrected in this BRD:

1. **`app/seams/source.py` — drop the `abstractmethod` import.** A `Protocol` does not use `@abstractmethod`. Importing it and not using it triggers `ruff F401`. The BRD's `SourceResult` class also has no need for `from abc import …`.
2. **`SourceResult` → use a Pydantic v2 model**, not a hand-rolled `__init__` / `to_dict` class. The whole codebase uses Pydantic v2 (`app/domain/events.py`, `app/domain/run.py`, `app/llm/models.py`); a stray non-Pydantic class is inconsistent. Use `BaseModel` with `model_config = ConfigDict(frozen=True)` and rely on `.model_dump()` instead of writing `to_dict`.
3. **`SourceError` — add type annotations** on `__init__` parameters (`source_type: SourceType`, `message: str`, `recoverable: bool = True`) — already in the BRD; just confirm they match `pyright --strict`.
4. **`base.py::BaseSource` — drop the abstract method redeclarations.** Each `@abstractmethod` in `BaseSource(ABC)` shadows the `Protocol`. Keep `BaseSource` as a *concrete* mixin that holds only the shared helper `_truncate_content`. Subclasses then `class TavilySource(BaseSource)` and the `Source` protocol is satisfied structurally (because of `@runtime_checkable`). This avoids the four-fold duplication of method signatures across `Source` / `BaseSource` / `TavilySource` / `WikipediaSource`.
5. **`tavily.py` — exception logging discipline.** `except Exception as e:` is acceptable here (catching the upstream lib's heterogeneous error set), but **chain** the original: `raise SourceError(...) from e`. Also do not put `str(e)` into `SourceError.message` directly without escaping — log details via `structlog.error("...", error=str(e))` and keep `SourceError.message` short.
6. **`tavily.py::health_check` — use a 1-result, 1-token request.** Hitting the API on every health check is expensive; document that this is a smoke check, not a liveness probe, and is **not** called on a hot path. The BRD's implementation is fine; just add the docstring note.
7. **`wikipedia.py` — wrap sync calls with `anyio.to_thread.run_sync`.** `wikipedia-api` is fully synchronous (uses `requests` under the hood). Calling it from an `async def` blocks the event loop. Wrap each blocking call:
   ```python
   import anyio
   page = await anyio.to_thread.run_sync(self._wiki.page, query)
   ```
   This is mandatory; the BRD's "we run it sync. For V2, consider anyio.to_thread" is wrong for V1 because the FSM (BRD-07) will call `search()` concurrently with other I/O.
8. **`wikipedia.py::_search_suggestions` — drop variations that mutate Wikipedia normalization.** `query.title()` and `query.lower()` rarely produce new results because `wikipediaapi.Wikipedia.page()` already normalizes. Keep only `[query, query.replace("_", " "), query.replace(" ", "_")]` (two variants, deduplicated by URL). Reduces network calls.
9. **`registry.py` — make it instance-friendly, not class-level mutable state.** The BRD uses class-level `_sources` and `_initialized`. That is a *singleton-with-classmethods* anti-pattern that makes test isolation painful. Use a **module-level lazy singleton**:
   ```python
   _registry: SourceRegistry | None = None
   def get_registry() -> SourceRegistry: ...
   ```
   `SourceRegistry` instances hold a `dict[SourceType, Source]`. The convenience `get_source(source_type)` reads from `get_registry()`.
   Provide `SourceRegistry.reset()` for tests.
10. **`registry.py::initialize` — do not instantiate `TavilySource()` if `TAVILY_API_KEY` is empty.** The constructor would crash on import in some test environments. Guard the instantiation; if the key is empty/missing, omit `TAVILY` from the registry and log a warning. Wikipedia has no key dependency and is always registered.
11. **`__init__.py` exports — match the existing project style** (`__all__` tuple) and avoid re-exporting `SourceError` from `sources/__init__.py` (it lives in `seams`, not in `sources` — keep the layer separation crisp).
12. **No `from typing import Dict`.** Use the built-in `dict[...]` (Python 3.12, project standard).

---

## 5. Detailed File Specifications

### 5.1 `backend/app/seams/source.py`

```python
"""Source plugin seam — one of three V1 extensibility points.

Sources retrieve evidence to answer research questions.
V1: Tavily (web search), Wikipedia.
V2 candidates: Confluence, arXiv, SQL.

Extension contract:
  - Implement the ``Source`` Protocol (or subclass ``BaseSource``).
  - Register the implementation in ``app.sources.registry``.
  - Add the identifier to ``SourceType`` enum.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import SourceType


class SourceResult(BaseModel):
    """A single result returned by a Source.search call."""

    model_config = ConfigDict(frozen=True)

    url: str
    title: str
    snippet: str
    content: str | None = None
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    published_date: str | None = None


class SourceError(Exception):
    """Raised when a source search or health check fails."""

    def __init__(
        self,
        source_type: SourceType,
        message: str,
        recoverable: bool = True,
    ) -> None:
        self.source_type = source_type
        self.message = message
        self.recoverable = recoverable
        super().__init__(message)


@runtime_checkable
class Source(Protocol):
    """Protocol for source plugins."""

    @property
    def source_type(self) -> SourceType: ...

    @property
    def name(self) -> str: ...

    async def search(self, query: str, max_results: int = 5) -> list[SourceResult]: ...

    async def health_check(self) -> bool: ...
```

### 5.2 `backend/app/seams/__init__.py`

```python
"""Plugin seams package.

V1 ships three seams:
  1. Source — data retrieval (this package)
  2. StoppingSignal — when to stop (BRD-09)
  3. OutputRenderer — answer formatting (BRD-16)
"""

from __future__ import annotations

from app.seams.source import Source, SourceError, SourceResult

__all__ = ("Source", "SourceError", "SourceResult")
```

### 5.3 `backend/app/sources/base.py`

```python
"""Shared helpers for source implementations."""

from __future__ import annotations

DEFAULT_MAX_CONTENT_CHARS = 5000


class BaseSource:
    """Concrete mixin with shared helpers.

    Subclasses must satisfy the ``Source`` Protocol structurally
    (no abstract methods are redeclared here on purpose).
    """

    def _truncate_content(self, content: str, max_chars: int = DEFAULT_MAX_CONTENT_CHARS) -> str:
        """Truncate ``content`` to at most ``max_chars`` characters."""
        if len(content) <= max_chars:
            return content
        return content[:max_chars] + "..."
```

### 5.4 `backend/app/sources/tavily.py`

```python
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
```

### 5.5 `backend/app/sources/wikipedia.py`

```python
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

    async def search(self, query: str, max_results: int = 5) -> list[SourceResult]:
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

    def _page_to_result(self, page: wikipediaapi.WikipediaPage, relevance_score: float) -> SourceResult:
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
```

### 5.6 `backend/app/sources/registry.py`

```python
"""Source registry — lazy module-level singleton."""

from __future__ import annotations

import structlog

from app.config import settings
from app.domain.enums import SourceType
from app.seams.source import Source
from app.sources.tavily import TavilySource
from app.sources.wikipedia import WikipediaSource

logger = structlog.get_logger(__name__)


class SourceRegistry:
    """Registry of available source plugins."""

    def __init__(self, sources: dict[SourceType, Source]) -> None:
        self._sources = sources

    @classmethod
    def build(cls) -> SourceRegistry:
        sources: dict[SourceType, Source] = {SourceType.WIKIPEDIA: WikipediaSource()}
        if settings.tavily_api_key:
            sources[SourceType.TAVILY] = TavilySource()
        else:
            logger.warning("tavily_disabled_missing_api_key")
        return cls(sources)

    def get(self, source_type: SourceType) -> Source:
        if source_type not in self._sources:
            raise ValueError(f"Unknown or disabled source type: {source_type}")
        return self._sources[source_type]

    def all(self) -> list[Source]:
        return list(self._sources.values())

    def types(self) -> list[SourceType]:
        return list(self._sources.keys())


_registry: SourceRegistry | None = None


def get_registry() -> SourceRegistry:
    global _registry
    if _registry is None:
        _registry = SourceRegistry.build()
    return _registry


def get_source(source_type: SourceType) -> Source:
    return get_registry().get(source_type)


def reset_registry() -> None:
    """Clear the cached registry (test-only)."""
    global _registry
    _registry = None
```

### 5.7 `backend/app/sources/__init__.py`

```python
"""Source plugins package."""

from __future__ import annotations

from app.sources.registry import (
    SourceRegistry,
    get_registry,
    get_source,
    reset_registry,
)
from app.sources.tavily import TavilySource
from app.sources.wikipedia import WikipediaSource

__all__ = (
    "SourceRegistry",
    "TavilySource",
    "WikipediaSource",
    "get_registry",
    "get_source",
    "reset_registry",
)
```

---

## 6. Implementation Sequence

| Step | Task | File | Priority |
|------|------|------|----------|
| 1 | Define seam: `SourceResult`, `SourceError`, `Source` Protocol. | `app/seams/source.py` | P0 |
| 2 | Re-export seam types. | `app/seams/__init__.py` | P0 |
| 3 | Implement `BaseSource` helper (truncation only). | `app/sources/base.py` | P0 |
| 4 | Implement `TavilySource`. | `app/sources/tavily.py` | P0 |
| 5 | Implement `WikipediaSource` with `anyio.to_thread`. | `app/sources/wikipedia.py` | P0 |
| 6 | Implement `SourceRegistry` (lazy singleton). | `app/sources/registry.py` | P0 |
| 7 | Re-export from `app/sources/__init__.py`. | `app/sources/__init__.py` | P0 |
| 8 | Unit tests (see §7). | `tests/test_seams_source.py`, `tests/test_sources_*.py` | P0 |
| 9 | Run `ruff check`, `pyright --strict`, and `pytest -q -p no:postgresql` until green. | — | P0 |

---

## 7. Testing Strategy (mandatory per L-002)

All tests are pure-Python with mocks — **no network access**.

### 7.1 `tests/test_seams_source.py`
- `test_source_result_is_frozen` — assignment after construction raises `ValidationError`.
- `test_source_result_serializes` — `.model_dump()` round-trips all fields.
- `test_source_result_validates_relevance_score_range` — `-0.1` and `1.1` rejected.
- `test_source_error_carries_metadata` — `source_type`, `message`, `recoverable` accessible.
- `test_source_protocol_is_runtime_checkable` — a fake satisfying the interface passes `isinstance(fake, Source)`.

### 7.2 `tests/test_sources_base.py`
- `test_truncate_short_string_unchanged`.
- `test_truncate_long_string_clipped_with_ellipsis`.
- `test_truncate_respects_max_chars_argument`.

### 7.3 `tests/test_sources_tavily.py`
Monkeypatch `TavilySource._client.search` with `AsyncMock`:
- `test_search_maps_api_response_to_source_results` — given a fake response dict with two items, returns two `SourceResult` with `url`, `title`, `snippet`, `content` populated.
- `test_search_truncates_content_to_5000_chars`.
- `test_search_clamps_max_results_between_1_and_10`.
- `test_search_passes_advanced_search_depth_and_includes_raw_content`.
- `test_search_raises_source_error_on_client_exception` — `recoverable=True`, `source_type=SourceType.TAVILY`, original exception is chained (`__cause__`).
- `test_search_handles_empty_results_list` — returns `[]`, no error.
- `test_health_check_returns_true_on_success` / `…false_on_exception`.

### 7.4 `tests/test_sources_wikipedia.py`
Monkeypatch `WikipediaSource._wiki.page` to return a stub object with `exists()`, `fullurl`, `title`, `summary`, `text`, `links` attributes. Use a small helper:

```python
@dataclass
class FakePage:
    title: str
    fullurl: str
    summary: str = ""
    text: str = ""
    links: dict[str, object] = field(default_factory=dict)
    _exists: bool = True

    def exists(self) -> bool:
        return self._exists
```

Tests:
- `test_search_returns_direct_match_when_page_exists`.
- `test_search_returns_linked_pages_up_to_max_results`.
- `test_search_falls_back_to_variations_when_page_missing` — `query.replace("_"," ")` succeeds.
- `test_search_truncates_content`.
- `test_search_raises_source_error_on_unexpected_exception`.
- `test_search_runs_sync_calls_off_the_event_loop` — assert `anyio.to_thread.run_sync` is awaited (patch and count calls).
- `test_health_check_returns_true_when_python_article_exists` / `…_false_on_exception`.

### 7.5 `tests/test_sources_registry.py`
Use `reset_registry()` in a fixture (autouse) to isolate tests.
- `test_get_returns_singleton_per_source_type` — `get(WIKIPEDIA) is get(WIKIPEDIA)`.
- `test_all_returns_all_registered` — contains Tavily and Wikipedia when key present.
- `test_tavily_omitted_when_api_key_missing` — monkeypatch `settings.tavily_api_key = ""`; registry has only Wikipedia; `get(TAVILY)` raises `ValueError`.
- `test_types_returns_source_type_list`.
- `test_get_source_convenience_function` — module-level `get_source(WIKIPEDIA)` returns the same instance as the registry.

### 7.6 Test isolation

Add to `tests/conftest.py` (only if needed by tests) an autouse fixture:

```python
@pytest.fixture(autouse=True)
def _reset_source_registry() -> Generator[None, None, None]:
    from app.sources.registry import reset_registry
    reset_registry()
    yield
    reset_registry()
```

But scope this fixture to `tests/test_sources_registry.py` only (place it at the top of the file, not in `conftest.py`) to avoid imposing import-time cost on unrelated suites.

### 7.7 Coverage target

≥ 90% line coverage for `app/seams/source.py` and `app/sources/*.py` combined (the bar from copilot-instructions §7.7 is 80%; this code is small enough to clear 90% easily).

---

## 8. Acceptance Criteria Mapping (BRD-06 §5)

| AC | Verifying test(s) |
|----|---|
| AC-01 Tavily search returns results | `test_sources_tavily.py::test_search_maps_api_response_to_source_results` |
| AC-02 Wikipedia search returns results | `test_sources_wikipedia.py::test_search_returns_direct_match_when_page_exists` + `…_returns_linked_pages_up_to_max_results` |
| AC-03 Registry provides all sources | `test_sources_registry.py::test_all_returns_all_registered` + `…_get_returns_singleton_per_source_type` |
| AC-04 Source errors are catchable | `test_sources_tavily.py::test_search_raises_source_error_on_client_exception` |
| AC-05 Health checks work | `test_sources_tavily.py::test_health_check_*` + `test_sources_wikipedia.py::test_health_check_*` |

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| `tavily-python` API shape differs across versions. | Pinned `>=0.5.0` in `pyproject.toml`; tests monkeypatch the client method, so any breaking change is caught by CI. |
| `wikipedia-api` is sync and could block the loop. | `anyio.to_thread.run_sync` for every blocking call (§5.5). Test asserts this (§7.4). |
| `wikipediaapi.Wikipedia` constructor changed signature (older versions required `language` positional). | Pin via `pyproject.toml`; pass `user_agent` and `language` as kwargs (forward-compatible). |
| `TavilySource` constructor crashes when `TAVILY_API_KEY` is empty at startup. | Registry guards instantiation (§4 deviation #10). Tests cover the missing-key path. |
| Wikipedia free-text variations explode the test fixture. | §4 deviation #8 limits to three deduplicated variants. |
| Class-level mutable state in registry (BRD §4.6) breaks test isolation. | Replaced with module-level lazy singleton + `reset_registry()` (§4 deviation #9). |

---

## 10. Definition of Done

- All 9 steps in §6 implemented.
- `ruff check backend/` clean.
- `pyright --strict` clean on changed files.
- `pytest backend/tests/test_seams_source.py backend/tests/test_sources_*.py -q -p no:postgresql` green.
- Full suite `pytest backend/tests/ -q -p no:postgresql` still green (no regressions).
- BRD-06 §6 checklist items 1-7 ticked; items 8 (unit tests) and 9 (integration) — unit tests delivered, integration marked manual-only.
- Reviewer score ≥ 9/10.
- Memory bank updated per Memory Protocol (`decisions-history.md`, `lessons-learned.md` if applicable, `knowledge-base-index.md`).

"""Source registry — lazy module-level singleton."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.config import settings
from app.domain.enums import SourceType
from app.sources.tavily import TavilySource
from app.sources.wikipedia import WikipediaSource

if TYPE_CHECKING:
    from app.seams.source import Source

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

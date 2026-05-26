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


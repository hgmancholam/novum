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

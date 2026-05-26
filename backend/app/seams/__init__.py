"""Plugin seams package.

V1 ships three seams:
  1. Source — data retrieval (this package)
  2. StoppingSignal — when to stop (BRD-09)
  3. OutputRenderer — answer formatting (BRD-16)
"""

from __future__ import annotations

from app.seams.source import Source, SourceError, SourceResult

__all__ = ("Source", "SourceError", "SourceResult")


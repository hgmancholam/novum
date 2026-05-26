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

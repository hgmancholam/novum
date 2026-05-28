"""Authority-tier classification for evidence sources (BRD-23 §4.7, WP-3).

Public surface:

- :func:`match` — classify a URL or host into an :class:`AuthorityTier`.
- :data:`AuthorityTier` — re-exported from :mod:`app.domain.enums` for convenience.
"""

from app.agent.sources_authority.tiers import match
from app.domain.enums import AuthorityTier

__all__ = ["AuthorityTier", "match"]

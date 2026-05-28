"""Static URL/host → :class:`AuthorityTier` rules (BRD-23 §4.7).

Pure, synchronous, no I/O. Rules are compiled once at import time and
applied in declaration order; first match wins. Anything not matched
falls back to :data:`AuthorityTier.GENERAL`.
"""

from __future__ import annotations

import re
from re import Pattern
from urllib.parse import urlparse

from app.domain.enums import AuthorityTier

_TIER_RULES: list[tuple[str, AuthorityTier]] = [
    # PRIMARY_AUTHORITATIVE
    # Government TLDs (English + Spanish/Latin, any country suffix).
    (r"(^|\.)gov$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"(^|\.)gov\.[a-z]{2,3}$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"(^|\.)gob$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"(^|\.)gob\.[a-z]{2,3}$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    # Military TLDs.
    (r"(^|\.)mil$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"(^|\.)mil\.[a-z]{2,3}$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    # International treaty organisations (restricted registry).
    (r"(^|\.)int$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    # Academic TLDs (any country suffix).
    (r"(^|\.)edu$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"(^|\.)edu\.[a-z]{2,3}$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"(^|\.)ac\.[a-z]{2,3}$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    # Specific authoritative hosts.
    (r"^who\.int$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"^nih\.gov$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"^ietf\.org$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"^iso\.org$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"^arxiv\.org$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    # Semantic Scholar: academic graph with peer-reviewed and preprint corpus.
    (r"(^|\.)semanticscholar\.org$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    (r"^doi\.org$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    # OpenAlex: open scholarly graph (200M+ works, fully free).
    (r"(^|\.)openalex\.org$", AuthorityTier.PRIMARY_AUTHORITATIVE),
    # REPUTABLE_SECONDARY
    (r"(^|\.)wikipedia\.org$", AuthorityTier.REPUTABLE_SECONDARY),
    (r"^britannica\.com$", AuthorityTier.REPUTABLE_SECONDARY),
    (r"^nytimes\.com$", AuthorityTier.REPUTABLE_SECONDARY),
    (r"^bbc\.(com|co\.uk)$", AuthorityTier.REPUTABLE_SECONDARY),
    (r"^reuters\.com$", AuthorityTier.REPUTABLE_SECONDARY),
    (r"^apnews\.com$", AuthorityTier.REPUTABLE_SECONDARY),
    # LOW_SIGNAL (Reddit deliberately left in GENERAL — BRD §15.3 Q3)
    (r"^medium\.com$", AuthorityTier.LOW_SIGNAL),
    (r"^quora\.com$", AuthorityTier.LOW_SIGNAL),
    (r"^answers\.com$", AuthorityTier.LOW_SIGNAL),
    (r"^geeksforgeeks\.org$", AuthorityTier.LOW_SIGNAL),
    (r"^w3schools\.com$", AuthorityTier.LOW_SIGNAL),
    (r"^tutorialspoint\.com$", AuthorityTier.LOW_SIGNAL),
    (r"^javatpoint\.com$", AuthorityTier.LOW_SIGNAL),
    (r"\.blogspot\.com$", AuthorityTier.LOW_SIGNAL),
    (r"\.wordpress\.com$", AuthorityTier.LOW_SIGNAL),
    (r"\.substack\.com$", AuthorityTier.LOW_SIGNAL),
    # Cheap/spam-prone TLDs. Generic — do not gate on country.
    (r"(^|\.)biz$", AuthorityTier.LOW_SIGNAL),
    (r"(^|\.)info$", AuthorityTier.LOW_SIGNAL),
    (r"(^|\.)xyz$", AuthorityTier.LOW_SIGNAL),
    (r"(^|\.)top$", AuthorityTier.LOW_SIGNAL),
]

_COMPILED: list[tuple[Pattern[str], AuthorityTier]] = [
    (re.compile(pattern), tier) for pattern, tier in _TIER_RULES
]


def _extract_host(source_url_or_host: str) -> str:
    """Lowercased host, stripped of ``www.`` prefix.

    Accepts both bare hosts (``example.com``) and full URLs
    (``https://www.example.com/path?q=1``).
    """
    candidate = source_url_or_host.strip().lower()
    if "://" in candidate:
        host = urlparse(candidate).hostname or ""
    else:
        # Treat the input as host[:port][/path]; trim path/port.
        host = candidate.split("/", 1)[0].split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def match(source_url_or_host: str) -> AuthorityTier:
    """Return the :class:`AuthorityTier` for *source_url_or_host*.

    First-match-wins over :data:`_TIER_RULES`. Unknown hosts return
    :data:`AuthorityTier.GENERAL`.
    """
    host = _extract_host(source_url_or_host)
    if not host:
        return AuthorityTier.GENERAL
    for pattern, tier in _COMPILED:
        if pattern.search(host):
            return tier
    return AuthorityTier.GENERAL

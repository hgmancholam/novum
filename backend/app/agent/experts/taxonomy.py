"""Expert taxonomy and domain matching for source credibility (US-22-3).

This module provides a static mapping of expert labels to domain patterns
and implements the matching logic for determining whether a source URL
belongs to an expected expert category. Used by `calculate_agreement` to
apply a non-compounding 1.1× credibility multiplier.

All functions are pure and deterministic.
"""

from __future__ import annotations

from urllib.parse import urlparse

import structlog

logger = structlog.get_logger(__name__)

# Static expert taxonomy (V1 ship-with-code).
# 12 expert types, 50 distinct domain patterns.
expert_taxonomy: dict[str, list[str]] = {
    "encyclopedia": [
        "wikipedia.org",
        "britannica.com",
        "encyclopedia.com",
    ],
    "geographer": [
        "nationalgeographic.com",
        "cia.gov",  # World Factbook
        "*.gov",  # generic gov authority for geography
    ],
    "nutritionist": [
        "mayoclinic.org",
        "eatright.org",
        "nutrition.org",
        "harvard.edu",  # T.H. Chan school of public health
    ],
    "medical_researcher": [
        "nih.gov",
        "pubmed.ncbi.nlm.nih.gov",
        "who.int",
        "thelancet.com",
        "nejm.org",
        "*.edu",  # academic medicine
    ],
    "database_engineer": [
        "postgresql.org",
        "mongodb.com",
        "use-the-index-luke.com",
        "martinfowler.com",
        "highscalability.com",
    ],
    "saas_architect": [
        "aws.amazon.com",
        "cloud.google.com",
        "azure.microsoft.com",
        "stripe.com",
        "vercel.com",
    ],
    "software_engineer": [
        "stackoverflow.com",
        "github.com",
        "developer.mozilla.org",
        "infoq.com",
        "thoughtworks.com",
    ],
    "academic_researcher": [
        "arxiv.org",
        "scholar.google.com",
        "acm.org",
        "ieee.org",
        "nature.com",
        "science.org",
        "*.edu",
    ],
    "industry_analyst": [
        "gartner.com",
        "forrester.com",
        "mckinsey.com",
        "bcg.com",
        "deloitte.com",
    ],
    "legal_scholar": [
        "law.cornell.edu",
        "scotusblog.com",
        "*.gov",
        "europa.eu",
    ],
    "economist": [
        "imf.org",
        "worldbank.org",
        "oecd.org",
        "federalreserve.gov",
        "ecb.europa.eu",
    ],
    "journalist": [
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "ft.com",
        "wsj.com",
    ],
}


def _normalize_host(url_or_host: str) -> str:
    """Normalize a URL or bare hostname to a lowercase host without www.

    Args:
        url_or_host: Full URL or bare hostname

    Returns:
        Normalized host string (e.g. "example.com"), or empty string on parse failure
    """
    try:
        # Add scheme if missing for urlparse to work correctly
        if "://" not in url_or_host:
            url_or_host = f"http://{url_or_host}"
        
        parsed = urlparse(url_or_host)
        # Use netloc if available, fall back to path for bare hosts
        host = parsed.netloc or parsed.path.split("/")[0]
        host = host.lower()
        
        # Strip leading www.
        if host.startswith("www."):
            host = host[4:]
        
        return host
    except Exception:
        return ""


def _pattern_matches(host: str, pattern: str) -> bool:
    """Check if a normalized host matches a pattern.

    Args:
        host: Normalized hostname (lowercase, no www.)
        pattern: Pattern from expert_taxonomy (may start with "*.")

    Returns:
        True if host matches pattern

    Matching rules:
        - Pattern "*.tld": matches any host ending with ".tld" or exactly "tld"
        - Other patterns: matches if host == pattern OR host ends with ".{pattern}"
        - Exception: www.{pattern} does NOT match (www. should be normalized away)
        - All comparisons case-insensitive
    """
    host = host.lower()
    pattern = pattern.lower()
    
    if pattern.startswith("*."):
        # TLD-family rule: *.gov matches nih.gov, cia.gov
        suffix = pattern[2:]  # Remove "*."
        return host == suffix or host.endswith(f".{suffix}")
    else:
        # Special case: www.{pattern} should NOT match (www. is normalized away)
        if host == f"www.{pattern}":
            return False
        # Exact suffix match: mayoclinic.org matches mayoclinic.org and health.mayoclinic.org
        return host == pattern or host.endswith(f".{pattern}")


def match(source_domain_or_url: str, expected_experts: list[str] | None) -> float:
    """Return credibility multiplier for a source based on expected expert match.

    Args:
        source_domain_or_url: Source URL or domain to check
        expected_experts: List of expert labels expected for the question (or None)

    Returns:
        1.1 if source matches any expected expert pattern, 1.0 otherwise

    Implementation notes:
        - Returns 1.0 if expected_experts is None or empty (no boost)
        - Iterates through experts; returns 1.1 on first pattern match
        - Unknown expert labels are logged (debug) and skipped
        - Never raises exceptions
        - Never compounds (returns on first match)
    """
    if not expected_experts:
        return 1.0
    
    host = _normalize_host(source_domain_or_url)
    if not host:
        return 1.0
    
    for expert_label in expected_experts:
        if expert_label not in expert_taxonomy:
            logger.debug("expert_label_unknown", label=expert_label)
            continue
        
        patterns = expert_taxonomy[expert_label]
        for pattern in patterns:
            if _pattern_matches(host, pattern):
                return 1.1
    
    return 1.0

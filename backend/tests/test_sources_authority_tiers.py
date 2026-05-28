"""BRD-23 §4.7 — Authority-tier classification tests."""

from __future__ import annotations

import pytest

from app.agent.sources_authority import AuthorityTier, match


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.cdc.gov/coronavirus", AuthorityTier.PRIMARY_AUTHORITATIVE),
        ("https://nasa.gov/", AuthorityTier.PRIMARY_AUTHORITATIVE),
        ("https://www.gov.uk/foo", AuthorityTier.PRIMARY_AUTHORITATIVE),
        ("https://mit.edu/research", AuthorityTier.PRIMARY_AUTHORITATIVE),
        ("https://www.ox.ac.uk/", AuthorityTier.PRIMARY_AUTHORITATIVE),
        ("https://who.int/data", AuthorityTier.PRIMARY_AUTHORITATIVE),
        ("https://arxiv.org/abs/2401.00001", AuthorityTier.PRIMARY_AUTHORITATIVE),
        ("https://iso.org/standard/1234", AuthorityTier.PRIMARY_AUTHORITATIVE),
        ("https://ietf.org/rfc/rfc1234", AuthorityTier.PRIMARY_AUTHORITATIVE),
    ],
)
def test_primary_authoritative_matches(url: str, expected: AuthorityTier) -> None:
    assert match(url) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://en.wikipedia.org/wiki/Python", AuthorityTier.REPUTABLE_SECONDARY),
        ("https://wikipedia.org/", AuthorityTier.REPUTABLE_SECONDARY),
        ("https://britannica.com/topic/foo", AuthorityTier.REPUTABLE_SECONDARY),
        ("https://nytimes.com/2024/01/01/", AuthorityTier.REPUTABLE_SECONDARY),
        ("https://bbc.co.uk/news/x", AuthorityTier.REPUTABLE_SECONDARY),
        ("https://bbc.com/sport", AuthorityTier.REPUTABLE_SECONDARY),
        ("https://reuters.com/world/", AuthorityTier.REPUTABLE_SECONDARY),
        ("https://apnews.com/article/foo", AuthorityTier.REPUTABLE_SECONDARY),
    ],
)
def test_reputable_secondary_matches(url: str, expected: AuthorityTier) -> None:
    assert match(url) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://medium.com/@alice/article", AuthorityTier.LOW_SIGNAL),
        ("https://quora.com/why-foo", AuthorityTier.LOW_SIGNAL),
        ("https://answers.com/q/foo", AuthorityTier.LOW_SIGNAL),
        ("https://geeksforgeeks.org/python-tutorial/", AuthorityTier.LOW_SIGNAL),
        ("https://w3schools.com/python", AuthorityTier.LOW_SIGNAL),
        ("https://tutorialspoint.com/python", AuthorityTier.LOW_SIGNAL),
        ("https://javatpoint.com/java", AuthorityTier.LOW_SIGNAL),
        ("https://alice.blogspot.com/2024/01/", AuthorityTier.LOW_SIGNAL),
        ("https://alice.wordpress.com/post", AuthorityTier.LOW_SIGNAL),
        ("https://alice.substack.com/p/foo", AuthorityTier.LOW_SIGNAL),
    ],
)
def test_low_signal_matches(url: str, expected: AuthorityTier) -> None:
    assert match(url) == expected


def test_reddit_stays_general_not_low_signal() -> None:
    """BRD §15.3 Q3 — Reddit kept in GENERAL on purpose."""
    assert match("https://reddit.com/r/Python/comments/abc") == AuthorityTier.GENERAL
    assert match("https://www.reddit.com/r/AskScience/") == AuthorityTier.GENERAL


def test_unknown_domain_general_fallback() -> None:
    assert match("https://example.com/foo") == AuthorityTier.GENERAL
    assert match("https://random-blog-site.io/post") == AuthorityTier.GENERAL


def test_url_with_path_query_and_fragment_extracts_host_only() -> None:
    url = "https://www.cdc.gov/foo/bar?x=1&y=2#section"
    assert match(url) == AuthorityTier.PRIMARY_AUTHORITATIVE


def test_www_prefix_stripped_and_case_insensitive() -> None:
    assert match("HTTPS://WWW.NIH.GOV/") == AuthorityTier.PRIMARY_AUTHORITATIVE
    assert match("WWW.MEDIUM.COM") == AuthorityTier.LOW_SIGNAL


def test_bare_host_input_supported() -> None:
    assert match("arxiv.org") == AuthorityTier.PRIMARY_AUTHORITATIVE
    assert match("medium.com") == AuthorityTier.LOW_SIGNAL


def test_empty_input_returns_general() -> None:
    assert match("") == AuthorityTier.GENERAL
    assert match("   ") == AuthorityTier.GENERAL

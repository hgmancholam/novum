"""LLM-driven domain allowlist for ``QuestionDomain.OTHER`` long-tail topics.

When the classifier emits :attr:`QuestionDomain.OTHER`, the static curated
whitelists in :mod:`app.agent.domain_allowlists` do not apply. This module
asks the ``CLASSIFIER`` LLM role (cheap, deterministic) to propose 3-8
authoritative web domains for the specific question, so Tavily searches
still benefit from a ``include_domains`` hint.

The result is cached on :attr:`RunState.dynamic_allowlist` and reused for
every sub-claim in the run — only **one** LLM call per run.
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, Field, model_validator

from app.llm import LLMRole, llm
from app.llm.models import _unwrap_schema_envelope

logger = structlog.get_logger(__name__)


class DynamicAllowlistOutput(BaseModel):
    """Structured output for the dynamic allowlist classifier prompt."""

    domains: list[str] = Field(default_factory=list, min_length=0, max_length=10)

    @model_validator(mode="before")
    @classmethod
    def _unwrap(cls, v: Any) -> Any:
        return _unwrap_schema_envelope(cls, v)


_PROMPT_TEMPLATE = (
    "You are helping route a web research query.\n"
    "For the following question, propose 3-8 authoritative or highly "
    "regarded web domains where expert content on this topic is published. "
    "Return BARE hostnames (no scheme, no path, no trailing slash). "
    "Prefer official organisations, peer-reviewed journals, established "
    "publications, government/academic sites, and well-curated communities. "
    "AVOID generic news aggregators, opinion blogs, marketing sites, and "
    "low-signal Q&A farms.\n\n"
    "Question: {question}"
)


def _sanitize(raw: str) -> str | None:
    """Normalise a candidate hostname; return None if it cannot be salvaged."""
    cleaned = raw.strip().lower().rstrip("/")
    # Strip schemes
    for prefix in ("https://", "http://", "www."):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    # Strip path segments
    cleaned = cleaned.split("/", 1)[0]
    # Reject obvious junk
    if "." not in cleaned or " " in cleaned or len(cleaned) < 4:
        return None
    return cleaned


async def propose_allowlist(question: str) -> list[str]:
    """Ask the classifier LLM for 3-8 authoritative domains for ``question``.

    Returns a sanitised, de-duplicated list. Returns an empty list on any
    failure — the caller treats that as "no allowlist, proceed open-web".
    """
    try:
        result = await llm.call(
            role=LLMRole.CLASSIFIER,
            messages=[{"role": "user", "content": _PROMPT_TEMPLATE.format(question=question)}],
            response_model=DynamicAllowlistOutput,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("dynamic_allowlist_llm_failed", error=str(exc))
        return []

    seen: set[str] = set()
    out: list[str] = []
    for raw in result.domains:
        cleaned = _sanitize(raw)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    logger.info("dynamic_allowlist_proposed", count=len(out), domains=out)
    return out

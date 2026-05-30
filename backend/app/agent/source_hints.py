"""Shared helper to build the ``**hints`` dict each Source.search call accepts.

Centralised so all call sites (search round, FAST lane, ReAct loop, CoVe
verifier) export the same classifier signals to the source plugins.
Sources pick the keys they understand and ignore the rest.
"""

from __future__ import annotations

from typing import Any

from app.agent.domain_allowlists import allowlist_for
from app.agent.run_state import RunState


def build_source_hints(state: RunState) -> dict[str, Any]:
    # IP-31: derive include_domains from the topical domain. Static curated
    # whitelist for the 11 known domains; LLM-proposed dynamic list (cached
    # on RunState) for QuestionDomain.OTHER. Tavily applies include_domains
    # as a strict filter, so search.py performs a retry without the hint
    # when the first call returns empty.
    static = list(allowlist_for(state.domain))
    include_domains = static if static else list(state.dynamic_allowlist)

    return {
        "language": state.language,
        "question_type": state.question_type.value if state.question_type else None,
        "expected_experts": list(state.expected_experts),
        "temporal_sensitivity": (
            state.temporal_sensitivity.value if state.temporal_sensitivity else None
        ),
        "complexity_hint": (
            state.complexity_hint.value if state.complexity_hint else None
        ),
        "domain": state.domain.value if state.domain else None,
        "include_domains": include_domains,
    }

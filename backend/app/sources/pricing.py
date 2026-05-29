"""Static pricing helpers for Source plugins (BRD-29 §4.2, IP-29 Task 1.6).

Pure helpers returning ``(units, unit_cost_usd, cost_usd)``.
"""

from __future__ import annotations

from app.config import settings


def tavily_cost(search_depth: str) -> tuple[int, float, float]:
    """Tavily: 1 credit for ``basic``, 2 for ``advanced``."""
    units = {"basic": 1, "advanced": 2}.get(search_depth, 1)
    unit = settings.tavily_usd_per_credit
    return units, unit, units * unit


def wikipedia_cost() -> tuple[int, float, float]:
    return 1, 0.0, 0.0


def free_source_cost() -> tuple[int, float, float]:
    return 1, 0.0, 0.0

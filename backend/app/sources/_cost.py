"""Shared cost-emit helper for Source plugins (BRD-29, IP-29 Task 1.7)."""

from __future__ import annotations

from typing import Literal

from app.domain.enums import EventType
from app.domain.events import CostIncurredEvent
from app.llm.context import current_emitter, current_task_name


async def emit_source_cost(
    *,
    provider: str,
    kind: Literal["search", "fetch"],
    units: int,
    unit_cost_usd: float,
    latency_ms: int,
) -> None:
    """Emit one ``CostIncurredEvent`` for a Source call.

    No-op when called outside a supervised run (``current_emitter`` unset).
    """
    emitter = current_emitter.get()
    if emitter is None:
        return
    task = current_task_name.get() or None
    event = CostIncurredEvent(
        type=EventType.COST_INCURRED,
        provider=provider,
        kind=kind,
        model=None,
        task_name=task,
        prompt_tokens=0,
        completion_tokens=0,
        units=units,
        unit_cost_usd=unit_cost_usd,
        cost_usd=units * unit_cost_usd,
        latency_ms=latency_ms,
        pricing_source="static",
    )
    await emitter(event)

"""Per-run context variables propagated through the async task tree.

Single-worker uvicorn + asyncio contextvar inheritance (RF-05) lets the
runner set these once at the root of ``_supervised_run`` and have every
nested LLM/Source call observe the same values without threading them
through every function signature.

See BRD-29 §4.8 (cost ledger plumbing) and RF-20.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from uuid import UUID

    from app.domain.events import BaseEvent


current_task: ContextVar[str] = ContextVar("current_task", default="")
"""FSM state name (orchestrator). Empty string when outside a transition."""

current_task_name: ContextVar[str] = current_task
"""Alias of :data:`current_task` — used by the cost ledger (BRD-29)."""

current_run_id: ContextVar[UUID | None] = ContextVar(
    "current_run_id", default=None
)
"""Run UUID set by the runner; ``None`` outside a supervised run."""

current_emitter: ContextVar[
    Callable[[BaseEvent], Awaitable[None]] | None
] = ContextVar("current_emitter", default=None)
"""Async event emitter; ``None`` when called outside a run (e.g. probes)."""

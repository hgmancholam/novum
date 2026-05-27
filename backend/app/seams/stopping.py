"""StoppingSignal plugin seam — second of three V1 extensibility points.

Stopping signals decide whether an agent run should ``CONTINUE`` more
research, ``DEFER`` to higher-priority signals, or ``STOP`` with a
canonical ``StopReason`` (RF-01, RF-04). The coordinating
``StoppingPolicy`` lives in ``app.stopping.policy``.

Extension contract:
  - Implement the ``StoppingSignal`` Protocol (no base class needed).
  - Pass the implementation to ``StoppingPolicy(signals=[...])`` or
    register it via the orchestrator's ``stopping_policy`` kwarg.

Frozen dataclasses are used for ``StopSignalOutput`` and ``StopContext``
because they are transient internal value objects — never persisted,
never serialised, never crossing process boundaries (mirrors
``app.confidence.mismatch.MismatchResult``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.domain.enums import StopReason


class SignalResult(StrEnum):
    """Outcome categories for a single stopping signal evaluation."""

    CONTINUE = "continue"
    STOP = "stop"
    DEFER = "defer"


@dataclass(frozen=True)
class StopSignalOutput:
    """Result returned by ``StoppingSignal.evaluate``.

    Invariant: ``result == STOP`` requires a non-``None`` ``stop_reason``
    (enforced in ``__post_init__``). This guarantees that
    ``stop_reason`` is always a canonical ``StopReason`` enum value
    whenever the policy decides to terminate (RF-02).
    """

    signal_name: str
    result: SignalResult
    stop_reason: StopReason | None = None
    explanation: str | None = None
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if self.result is SignalResult.STOP and self.stop_reason is None:
            raise ValueError(
                "StopSignalOutput with result=STOP requires a non-None stop_reason"
            )


@dataclass(frozen=True)
class StopContext:
    """Immutable snapshot of run state passed to every signal.

    Built once per ``StoppingPolicy.evaluate`` call so that all signals
    observe the same view of the world (avoids drift across the
    priority loop and ensures structural confidence is computed once).
    """

    coverage: float
    agreement: float
    diversity: float
    no_conflict: float
    structural_confidence: float
    judge_confidence: float | None
    threshold: float
    search_count: int
    max_searches: int
    has_contradictions: bool
    has_ambiguity: bool
    uncoverable_claims: int
    covered_claims: int
    total_claims: int


@runtime_checkable
class StoppingSignal(Protocol):
    """Protocol for stopping-signal plugins."""

    @property
    def name(self) -> str: ...

    @property
    def priority(self) -> int: ...

    async def evaluate(self, context: StopContext) -> StopSignalOutput: ...

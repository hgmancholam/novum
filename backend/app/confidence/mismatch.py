"""S/J mismatch detection (RF-15).

Lightweight, synchronous helper used by the orchestrator to decide when
to emit a ``ConfidenceMismatchEvent``. The result type is a frozen
dataclass because it is a transient internal helper that never crosses
process boundaries (IP-08 O-06).
"""

from __future__ import annotations

from dataclasses import dataclass

_STRUCTURAL_HIGHER_FLAG = (
    "Structural metrics ({s:.0%}) exceed judge assessment ({j:.0%}). "
    "Judge may have identified issues not captured in automated scoring."
)
_JUDGE_HIGHER_FLAG = (
    "Judge assessment ({j:.0%}) exceeds structural metrics ({s:.0%}). "
    "Evidence may be stronger than coverage metrics suggest."
)


@dataclass(frozen=True)
class MismatchResult:
    """Outcome of comparing structural (S) and judge (J) confidences."""

    has_mismatch: bool
    structural: float
    judge: float
    divergence: float
    trust_flag: str | None


def detect_mismatch(
    structural: float, judge: float, threshold: float = 0.2
) -> MismatchResult:
    """Return whether ``|S - J|`` exceeds ``threshold`` and a trust flag."""
    divergence = abs(structural - judge)
    has_mismatch = divergence > threshold
    trust_flag: str | None = None
    if has_mismatch:
        if structural > judge:
            trust_flag = _STRUCTURAL_HIGHER_FLAG.format(s=structural, j=judge)
        else:
            trust_flag = _JUDGE_HIGHER_FLAG.format(s=structural, j=judge)
    return MismatchResult(
        has_mismatch=has_mismatch,
        structural=structural,
        judge=judge,
        divergence=divergence,
        trust_flag=trust_flag,
    )

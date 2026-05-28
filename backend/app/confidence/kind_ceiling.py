"""Per-AnswerKind confidence ceilings (RF-12, WP-3, BRD-23 WP-1).

Each ``AnswerKind`` carries an epistemic ceiling reflecting the inherent
uncertainty of its answer shape. ``S_effective = S_raw · kind_ceiling[kind]``
before entering ``final_confidence = min(S_effective, J)``.

BRD-23 WP-1: when AnswerKind == DIRECT and the run's temporal_sensitivity
is volatile/realtime AND >= 50% of evidence rows have a stale
``source_published_date`` (older than the active Tavily days filter), the
ceiling is multiplied by ``settings.temporal_stale_penalty`` (= 0.85).
The penalty only LOWERS the ceiling; it never raises it.
"""

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.config import settings
from app.domain.enums import AnswerKind, TemporalSensitivity

if TYPE_CHECKING:
    from app.agent.run_state import EvidenceItem

# Per confidence-calculation.md amendment (2026-05-27), Table 1
KIND_CEILING: dict[AnswerKind, float] = {
    AnswerKind.DIRECT: 1.00,
    AnswerKind.WEIGHTED: 0.85,
    AnswerKind.SCENARIO: 0.60,
    AnswerKind.TRADEOFF: 0.70,
    AnswerKind.BEST_EFFORT: 0.55,
    AnswerKind.ETHICAL_REDIRECT: 0.50,  # Not gated but present for completeness
}


def is_stale_majority(
    evidence: list["EvidenceItem"],
    days_filter: int | None,
) -> bool:
    """BRD-23 WP-1: >= 50% of evidence rows have a stale ``source_published_date``.

    Rows whose date is missing AND ``days_filter`` is not None count as stale.
    Returns False when ``days_filter`` is None or evidence is empty.
    """
    if days_filter is None or not evidence:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_filter)
    stale = 0
    for ev in evidence:
        published = getattr(ev, "source_published_date", None)
        if published is None:
            stale += 1
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if published < cutoff:
            stale += 1
    return stale * 2 >= len(evidence)


def apply_ceiling(
    structural_raw: float,
    answer_kind: AnswerKind,
    *,
    temporal_sensitivity: TemporalSensitivity | None = None,
    stale_majority: bool = False,
) -> float:
    """Apply the kind-specific ceiling to the raw structural score.

    Args:
        structural_raw: S_raw ∈ [0.0, 1.0]
        answer_kind: The selected AnswerKind
        temporal_sensitivity: BRD-23 WP-1 temporal label (optional)
        stale_majority: BRD-23 WP-1 flag computed via ``is_stale_majority``

    Returns:
        S_effective = S_raw · kind_ceiling[answer_kind] · stale_penalty?
    """
    ceiling = KIND_CEILING.get(answer_kind, 1.0)
    if (
        answer_kind == AnswerKind.DIRECT
        and stale_majority
        and temporal_sensitivity
        in (TemporalSensitivity.VOLATILE, TemporalSensitivity.REALTIME)
    ):
        ceiling *= settings.temporal_stale_penalty
    return structural_raw * ceiling

"""Per-AnswerKind confidence ceilings (RF-12, WP-3).

Each ``AnswerKind`` carries an epistemic ceiling reflecting the inherent
uncertainty of its answer shape. ``S_effective = S_raw · kind_ceiling[kind]``
before entering ``final_confidence = min(S_effective, J)``.
"""

from app.domain.enums import AnswerKind

# Per confidence-calculation.md amendment (2026-05-27), Table 1
KIND_CEILING: dict[AnswerKind, float] = {
    AnswerKind.DIRECT: 1.00,
    AnswerKind.WEIGHTED: 0.85,
    AnswerKind.SCENARIO: 0.60,
    AnswerKind.TRADEOFF: 0.70,
    AnswerKind.BEST_EFFORT: 0.55,
    AnswerKind.ETHICAL_REDIRECT: 0.50,  # Not gated but present for completeness
}


def apply_ceiling(structural_raw: float, answer_kind: AnswerKind) -> float:
    """Apply the kind-specific ceiling to the raw structural score.

    Args:
        structural_raw: S_raw ∈ [0.0, 1.0]
        answer_kind: The selected AnswerKind

    Returns:
        S_effective = S_raw · kind_ceiling[answer_kind]
    """
    ceiling = KIND_CEILING.get(answer_kind, 1.0)
    return structural_raw * ceiling

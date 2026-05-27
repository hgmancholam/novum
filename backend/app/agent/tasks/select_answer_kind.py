"""Deterministic ``AnswerKind`` resolver (RF-17; consumed by WP-2)."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import AnswerKind, QuestionType


@dataclass(frozen=True, slots=True)
class AnswerKindInputs:
    """Inputs to :func:`select_answer_kind`. All scores in ``[0, 1]``."""

    question_type: QuestionType
    structural_confidence: float
    coverage: float
    agreement: float
    ambiguity_flag: bool = False


_DIRECT_MIN_S = 0.75
_DIRECT_MIN_COVERAGE = 1.0
_DIRECT_MIN_AGREEMENT = 0.6
_WEIGHTED_AGREEMENT_CEILING = 0.6
_BEST_EFFORT_COVERAGE_FLOOR = 0.5


def select_answer_kind(inputs: AnswerKindInputs) -> AnswerKind:
    """Return the ``AnswerKind`` for the given run state (deterministic).

    Priority order:
      1. ``personal_private``     → ``ETHICAL_REDIRECT``
      2. ``predictive_future``    → ``SCENARIO``
      3. ``subjective_opinion``   → ``TRADEOFF``
      4. ambiguity OR cov < 0.5   → ``BEST_EFFORT``
      5. cov complete, agr < 0.6  → ``WEIGHTED``
      6. cov complete, S ≥ 0.75,
         agr ≥ 0.6                → ``DIRECT``
      7. else                     → ``BEST_EFFORT``
    """
    match inputs.question_type:
        case QuestionType.PERSONAL_PRIVATE:
            return AnswerKind.ETHICAL_REDIRECT
        case QuestionType.PREDICTIVE_FUTURE:
            return AnswerKind.SCENARIO
        case QuestionType.SUBJECTIVE_OPINION:
            return AnswerKind.TRADEOFF
        case _:
            pass

    if inputs.ambiguity_flag or inputs.coverage < _BEST_EFFORT_COVERAGE_FLOOR:
        return AnswerKind.BEST_EFFORT

    coverage_complete = inputs.coverage >= _DIRECT_MIN_COVERAGE
    if coverage_complete and inputs.agreement < _WEIGHTED_AGREEMENT_CEILING:
        return AnswerKind.WEIGHTED
    if (
        coverage_complete
        and inputs.structural_confidence >= _DIRECT_MIN_S
        and inputs.agreement >= _DIRECT_MIN_AGREEMENT
    ):
        return AnswerKind.DIRECT
    return AnswerKind.BEST_EFFORT


__all__ = ("AnswerKindInputs", "select_answer_kind")

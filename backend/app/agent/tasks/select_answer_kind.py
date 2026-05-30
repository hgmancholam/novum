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

    Priority order (IP-33 — question-type templates win over partial
    coverage; the synthesizer prompt hedges in the Bottom Line when
    evidence is incomplete):

      1. ``personal_private``                          → ``ETHICAL_REDIRECT``
      2. ``ambiguity_flag``                            → ``BEST_EFFORT``
         (keeps empty-criteria comparatives like "best X" routing right)
      3. ``predictive_future``                         → ``SCENARIO``
      4. ``comparative``                               → ``WEIGHTED``
      5. ``subjective_opinion``                        → ``TRADEOFF``
      6. ``state_of_art`` with cov ≥ 0.5               → ``WEIGHTED``
         (state-of-art is inherently a comparison of leading approaches)
      7. For the remaining ``factual`` / ``definitional`` / ``causal``:
         a. cov < 0.5                                  → ``BEST_EFFORT``
         b. cov complete, agr < 0.6                    → ``WEIGHTED``
         c. cov complete, S ≥ 0.75, agr ≥ 0.6         → ``DIRECT``
         d. else                                       → ``BEST_EFFORT``
    """
    if inputs.question_type == QuestionType.PERSONAL_PRIVATE:
        return AnswerKind.ETHICAL_REDIRECT

    if inputs.ambiguity_flag:
        return AnswerKind.BEST_EFFORT

    match inputs.question_type:
        case QuestionType.PREDICTIVE_FUTURE:
            return AnswerKind.SCENARIO
        case QuestionType.COMPARATIVE:
            return AnswerKind.WEIGHTED
        case QuestionType.SUBJECTIVE_OPINION:
            return AnswerKind.TRADEOFF
        case QuestionType.STATE_OF_ART if inputs.coverage >= _BEST_EFFORT_COVERAGE_FLOOR:
            return AnswerKind.WEIGHTED
        case _:
            pass

    if inputs.coverage < _BEST_EFFORT_COVERAGE_FLOOR:
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

"""Unit tests for the AnswerKind resolver (RF-17, WP-1)."""

from __future__ import annotations

import pytest

from app.agent.tasks.select_answer_kind import (
    AnswerKindInputs,
    select_answer_kind,
)
from app.domain.enums import AnswerKind, QuestionType


def test_personal_private_routes_to_ethical_redirect() -> None:
    out = select_answer_kind(
        AnswerKindInputs(
            question_type=QuestionType.PERSONAL_PRIVATE,
            structural_confidence=0.9,
            coverage=1.0,
            agreement=1.0,
            ambiguity_flag=False,
        )
    )
    assert out is AnswerKind.ETHICAL_REDIRECT


def test_predictive_future_routes_to_scenario() -> None:
    out = select_answer_kind(
        AnswerKindInputs(
            question_type=QuestionType.PREDICTIVE_FUTURE,
            structural_confidence=0.9,
            coverage=1.0,
            agreement=1.0,
            ambiguity_flag=False,
        )
    )
    assert out is AnswerKind.SCENARIO


def test_subjective_opinion_routes_to_tradeoff() -> None:
    out = select_answer_kind(
        AnswerKindInputs(
            question_type=QuestionType.SUBJECTIVE_OPINION,
            structural_confidence=0.9,
            coverage=1.0,
            agreement=1.0,
            ambiguity_flag=False,
        )
    )
    assert out is AnswerKind.TRADEOFF


def test_factual_with_good_evidence_routes_to_direct() -> None:
    out = select_answer_kind(
        AnswerKindInputs(
            question_type=QuestionType.FACTUAL,
            structural_confidence=0.8,
            coverage=1.0,
            agreement=0.7,
            ambiguity_flag=False,
        )
    )
    assert out is AnswerKind.DIRECT


def test_comparative_low_agreement_routes_to_weighted() -> None:
    out = select_answer_kind(
        AnswerKindInputs(
            question_type=QuestionType.COMPARATIVE,
            structural_confidence=0.6,
            coverage=1.0,
            agreement=0.4,
            ambiguity_flag=False,
        )
    )
    assert out is AnswerKind.WEIGHTED


def test_factual_low_coverage_routes_to_best_effort() -> None:
    out = select_answer_kind(
        AnswerKindInputs(
            question_type=QuestionType.FACTUAL,
            structural_confidence=0.9,
            coverage=0.4,
            agreement=1.0,
            ambiguity_flag=False,
        )
    )
    assert out is AnswerKind.BEST_EFFORT


def test_ambiguity_flag_overrides_to_best_effort() -> None:
    out = select_answer_kind(
        AnswerKindInputs(
            question_type=QuestionType.STATE_OF_ART,
            structural_confidence=0.9,
            coverage=1.0,
            agreement=0.9,
            ambiguity_flag=True,
        )
    )
    assert out is AnswerKind.BEST_EFFORT


def test_causal_below_direct_threshold_falls_through_to_best_effort() -> None:
    """S=0.7 < 0.75 DIRECT floor, agr=0.7 >= 0.6 WEIGHTED ceiling → BEST_EFFORT."""
    out = select_answer_kind(
        AnswerKindInputs(
            question_type=QuestionType.CAUSAL,
            structural_confidence=0.7,
            coverage=1.0,
            agreement=0.7,
            ambiguity_flag=False,
        )
    )
    assert out is AnswerKind.BEST_EFFORT


@pytest.mark.parametrize(
    ("qtype", "expected"),
    [
        (QuestionType.PERSONAL_PRIVATE, AnswerKind.ETHICAL_REDIRECT),
        (QuestionType.PREDICTIVE_FUTURE, AnswerKind.SCENARIO),
        (QuestionType.SUBJECTIVE_OPINION, AnswerKind.TRADEOFF),
        (QuestionType.FACTUAL, AnswerKind.DIRECT),
        # COMPARATIVE always routes to WEIGHTED per IP-21 §0.8 (rows 2 & 6):
        # comparisons are inherently tradeoff framings, even when sources agree.
        (QuestionType.COMPARATIVE, AnswerKind.WEIGHTED),
        (QuestionType.DEFINITIONAL, AnswerKind.DIRECT),
        (QuestionType.STATE_OF_ART, AnswerKind.DIRECT),
        (QuestionType.CAUSAL, AnswerKind.DIRECT),
    ],
)
def test_all_question_types_have_a_good_path(
    qtype: QuestionType, expected: AnswerKind
) -> None:
    """Every QuestionType resolves to a defensible AnswerKind on the good path."""
    out = select_answer_kind(
        AnswerKindInputs(
            question_type=qtype,
            structural_confidence=0.85,
            coverage=1.0,
            agreement=0.8,
            ambiguity_flag=False,
        )
    )
    assert out is expected

"""G13 resolver acceptance test — §0.8 matrix from IP-21 (WP-3).

Validates that the resolver selects the correct AnswerKind for every
combination of (question_type, ambiguity, coverage, agreement, has_contradiction).
Each row is one test case parametrized via pytest.
"""

import pytest

from app.agent.tasks.select_answer_kind import AnswerKindInputs, select_answer_kind
from app.domain.enums import AnswerKind, QuestionType


# yapf: disable
@pytest.mark.parametrize(
    "question_type,s_raw,coverage,agreement,ambiguity,expected_kind",
    [
        # Row 1: Capital of Japan — factual, full coverage
        (QuestionType.FACTUAL, 0.95, 1.0, 1.0, False, AnswerKind.DIRECT),
        # Row 2: PostgreSQL vs MongoDB — comparative, agr<0.6 → WEIGHTED
        (QuestionType.COMPARATIVE, 0.70, 1.0, 0.55, False, AnswerKind.WEIGHTED),
        # Row 3: Best programming language — ambiguous comparative
        (QuestionType.COMPARATIVE, 0.60, 0.8, 0.5, True, AnswerKind.BEST_EFFORT),
        # Row 4: Intermittent fasting — causal, agr<0.6, cov complete
        (QuestionType.CAUSAL, 0.65, 1.0, 0.45, False, AnswerKind.WEIGHTED),
        # Row 5: Long-term AI risks — predictive priority wins
        (QuestionType.PREDICTIVE_FUTURE, 0.60, 0.7, 0.6, False, AnswerKind.SCENARIO),
        # Row 6: EDA vs microservices — comparative, agr<0.6
        (QuestionType.COMPARATIVE, 0.70, 1.0, 0.55, False, AnswerKind.WEIGHTED),
        # Row 7: Long-term memory for AI agents — state_of_art, cov=0.6 → BEST_EFFORT
        (QuestionType.STATE_OF_ART, 0.55, 0.6, 0.55, False, AnswerKind.BEST_EFFORT),
        # Row 8: AI replacing engineers — predictive priority wins
        (QuestionType.PREDICTIVE_FUTURE, 0.50, 0.7, 0.4, False, AnswerKind.SCENARIO),
    ],
)
# yapf: enable
def test_resolver_acceptance_matrix(
    question_type: QuestionType,
    s_raw: float,
    coverage: float,
    agreement: float,
    ambiguity: bool,
    expected_kind: AnswerKind,
) -> None:
    """Validate resolver decision matrix per IP-21 §0.8 (WP-3 G13)."""
    inputs = AnswerKindInputs(
        question_type=question_type,
        structural_confidence=s_raw,
        coverage=coverage,
        agreement=agreement,
        ambiguity_flag=ambiguity,
    )
    result = select_answer_kind(inputs)
    assert result == expected_kind, (
        f"Resolver mismatch for (QT={question_type.value}, S={s_raw}, "
        f"cov={coverage}, agr={agreement}, amb={ambiguity}): "
        f"expected {expected_kind.value}, got {result.value}"
    )


def test_resolver_ethical_redirect() -> None:
    """PERSONAL_PRIVATE always routes to ETHICAL_REDIRECT (RF-17)."""
    inputs = AnswerKindInputs(
        question_type=QuestionType.PERSONAL_PRIVATE,
        structural_confidence=0.0,
        coverage=0.0,
        agreement=0.0,
        ambiguity_flag=False,
    )
    result = select_answer_kind(inputs)
    assert result == AnswerKind.ETHICAL_REDIRECT

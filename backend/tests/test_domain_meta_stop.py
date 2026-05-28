"""Unit tests for ``app.domain.meta_stop`` Pydantic models (BRD-26)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.meta_stop import (
    AdversarialCompletenessVerdict,
    Objection,
    ValueOfContinuationVerdict,
)


def test_voc_verdict_accepts_three_decisions() -> None:
    for decision in ("stop", "continue", "stop_best_effort"):
        v = ValueOfContinuationVerdict(
            decision=decision,  # type: ignore[arg-type]
            expected_delta_s=0.1,
            next_action_hypothesis=None,
            reason="ok",
        )
        assert v.decision == decision


def test_voc_verdict_rejects_bad_delta() -> None:
    with pytest.raises(ValidationError):
        ValueOfContinuationVerdict(
            decision="stop",
            expected_delta_s=1.5,
            next_action_hypothesis=None,
            reason="ok",
        )


def test_voc_verdict_requires_reason() -> None:
    with pytest.raises(ValidationError):
        ValueOfContinuationVerdict(
            decision="stop",
            expected_delta_s=0.0,
            next_action_hypothesis=None,
            reason="",
        )


def _obj(status: str = "answered_by_evidence") -> Objection:
    return Objection(text="x", status=status, evidence_ids_answering=[uuid4()])  # type: ignore[arg-type]


def test_adversarial_verdict_requires_exactly_three() -> None:
    with pytest.raises(ValidationError):
        AdversarialCompletenessVerdict(objections=[_obj()])
    with pytest.raises(ValidationError):
        AdversarialCompletenessVerdict(objections=[_obj(), _obj(), _obj(), _obj()])


def test_adversarial_verdict_derives_all_answered() -> None:
    v = AdversarialCompletenessVerdict(objections=[_obj(), _obj(), _obj()])
    assert v.all_answered is True

    v2 = AdversarialCompletenessVerdict(
        objections=[_obj(), _obj("unanswered_needs_search"), _obj()]
    )
    assert v2.all_answered is False


def test_extra_fields_allowed_for_replay_safety() -> None:
    v = ValueOfContinuationVerdict(
        decision="stop",
        expected_delta_s=0.0,
        next_action_hypothesis=None,
        reason="r",
        future_field="x",  # type: ignore[call-arg]
    )
    assert v.decision == "stop"

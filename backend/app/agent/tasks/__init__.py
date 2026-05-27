"""Agent task entry points."""

from __future__ import annotations

from app.agent.tasks.analyze import analyze_evidence
from app.agent.tasks.classify import classify_question
from app.agent.tasks.draft import (
    draft_answer,
    evaluate_with_judge,
    map_issues_to_claims,
)
from app.agent.tasks.normalize import normalize_question
from app.agent.tasks.plan import create_plan, critique_plan, revise_plan
from app.agent.tasks.search import execute_search_round
from app.agent.tasks.select_answer_kind import (
    AnswerKindInputs,
    select_answer_kind,
)

__all__ = (
    "AnswerKindInputs",
    "analyze_evidence",
    "classify_question",
    "create_plan",
    "critique_plan",
    "draft_answer",
    "evaluate_with_judge",
    "execute_search_round",
    "map_issues_to_claims",
    "normalize_question",
    "revise_plan",
    "select_answer_kind",
)

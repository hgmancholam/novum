"""Abductive hypothesis generation for causal/scenario questions (IP-25 Phase D).

Generates 2-4 competing hypotheses when:
- question_type in {CAUSAL, SCENARIO, PREDICTIVE_FUTURE, BEST_EFFORT}
- OR selected_lane == DEEP
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from app.agent.run_state import RunState
from app.domain.hypothesis import Hypothesis
from app.llm import LLMRole, llm

logger = structlog.get_logger()


class HypothesisDraft(BaseModel):
    """Draft hypothesis from LLM (no UUID yet)."""

    text: str
    priority: float = Field(ge=0.0, le=1.0)


class HypothesesList(BaseModel):
    """Container for LLM-generated hypotheses."""

    items: list[HypothesisDraft]


async def generate_hypotheses(state: RunState) -> list[Hypothesis]:
    """Generate 2-4 competing hypotheses for the question.

    Args:
        state: Current run state with question and question_type

    Returns:
        List of 2-4 Hypothesis objects with unique UUIDs

    Raises:
        ValueError: If LLM returns < 2 hypotheses
    """
    logger.info(
        "Generating abductive hypotheses",
        run_id=str(state.run_id),
        question_type=state.question_type,
    )

    from app.llm.prompts import HYPOTHESES_PROMPT

    response = await llm.call(
        role=LLMRole.PLANNER,
        messages=[
            {"role": "system", "content": HYPOTHESES_PROMPT},
            {"role": "user", "content": state.question},
        ],
        response_model=HypothesesList,
    )

    drafts = response.items

    if len(drafts) < 2:
        logger.error(
            "LLM returned insufficient hypotheses",
            count=len(drafts),
            run_id=str(state.run_id),
        )
        raise ValueError(f"Expected at least 2 hypotheses, got {len(drafts)}")

    # Clamp to 2-4 range
    drafts = drafts[:4]

    # Convert to Hypothesis with UUIDs
    hypotheses = [
        Hypothesis(
            text=draft.text,
            priority=draft.priority,
        )
        for draft in drafts
    ]

    logger.info(
        "Generated hypotheses",
        run_id=str(state.run_id),
        count=len(hypotheses),
    )

    return hypotheses

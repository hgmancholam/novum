"""History management for ReAct loop (IP-25 Phase E T-25-E-04).

Implements token-aware history summarization to prevent context overflow.
Uses tiktoken (cl100k_base) for token counting and synthesizer role for
summarization when history exceeds max_tokens threshold.
"""

from __future__ import annotations

import structlog
import tiktoken
from pydantic import BaseModel, ConfigDict

from app.agent.react.actions import AgentActionUnion, FinishAction
from app.llm import LLMRole, llm

logger = structlog.get_logger()

# cl100k_base is the encoding used by gpt-4/gpt-3.5-turbo
_TOKENIZER = tiktoken.get_encoding("cl100k_base")


class ReactStep(BaseModel):
    """Single step in the ReAct loop history."""

    model_config = ConfigDict(extra="allow")

    step: int
    thought: str
    action: AgentActionUnion
    observation: str


class HistorySummary(BaseModel):
    """LLM response for history summarization."""

    summary: str


def _count_tokens(text: str) -> int:
    """Count tokens in text using cl100k_base encoding."""
    return len(_TOKENIZER.encode(text))


def _history_to_text(history: list[ReactStep]) -> str:
    """Convert history steps to concatenated text for token counting."""
    parts: list[str] = []
    for step in history:
        parts.append(f"Step {step.step}:")
        parts.append(f"Thought: {step.thought}")
        parts.append(f"Action: {step.action.type}")
        parts.append(f"Observation: {step.observation}")
    return "\n".join(parts)


async def summarize_history_if_needed(
    history: list[ReactStep],
    max_tokens: int = 15000,
) -> tuple[list[ReactStep], int | None]:
    """Summarize history if token count exceeds threshold.

    Args:
        history: Complete ReAct loop history
        max_tokens: Token threshold for triggering summarization (default 15000)

    Returns:
        Tuple of (possibly summarized history, steps_summarized or None)

    Logic:
        1. Count tokens in concatenated history
        2. If <= max_tokens: return original history unchanged
        3. If > max_tokens:
           a. Keep last 4 steps verbatim (recent context)
           b. Summarize everything before that with SYNTHESIZER role
           c. Create synthetic ReactStep with step=-1 and summary content
           d. Return [synthetic_step] + last_4_steps
    """
    if not history:
        return history, None

    history_text = _history_to_text(history)
    token_count = _count_tokens(history_text)

    if token_count <= max_tokens:
        logger.debug(
            "react_history_within_budget",
            token_count=token_count,
            max_tokens=max_tokens,
            steps=len(history),
        )
        return history, None

    # Need to summarize — keep last 4 steps, summarize the rest
    keep_last_n = 4
    if len(history) <= keep_last_n:
        # Not enough steps to benefit from summarization
        return history, None

    steps_to_summarize = history[:-keep_last_n]
    steps_to_keep = history[-keep_last_n:]

    logger.info(
        "react_history_summarization_triggered",
        total_steps=len(history),
        steps_to_summarize=len(steps_to_summarize),
        steps_to_keep=len(steps_to_keep),
        token_count=token_count,
        max_tokens=max_tokens,
    )

    # Build text to summarize
    summarize_text = _history_to_text(steps_to_summarize)

    # Call LLM for summarization
    from app.agent.react.prompts import REACT_HISTORY_SUMMARIZATION_PROMPT

    try:
        response = await llm.call(
            role=LLMRole.SYNTHESIZER,
            messages=[
                {
                    "role": "system",
                    "content": REACT_HISTORY_SUMMARIZATION_PROMPT.format(
                        history_text=summarize_text
                    ),
                },
                {"role": "user", "content": "Summarize the history above."},
            ],
            response_model=HistorySummary,
        )

        summary = response.summary

        # Create synthetic step with step=-1
        synthetic_step = ReactStep(
            step=-1,
            thought=summary,
            action=FinishAction(reason="history_summary_placeholder"),
            observation="",
        )

        summarized_history = [synthetic_step] + steps_to_keep

        logger.info(
            "react_history_summarized",
            steps_summarized=len(steps_to_summarize),
            summary_tokens=_count_tokens(summary),
            new_history_length=len(summarized_history),
        )

        return summarized_history, len(steps_to_summarize)

    except Exception as exc:
        logger.warning(
            "react_history_summarization_failed",
            error=str(exc),
            falling_back_to_truncation=True,
        )
        # Fallback: just keep last 4 steps
        return steps_to_keep, len(steps_to_summarize)

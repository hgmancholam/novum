"""PR-7 invariant: judge prompts must carry the language-policy clause.

Empirical eval (2026-05-29) showed the judge rejecting valid Spanish answers
to English questions with rationales like "answer is written in Spanish while
the question is in English". The clause exists to prevent that regression;
this test guards it from being silently removed in future prompt rewrites.
"""

from app.llm.prompts import FAST_MINI_JUDGE_PROMPT, JUDGE_SYSTEM_PROMPT


def test_judge_system_prompt_has_language_policy() -> None:
    assert "Language policy" in JUDGE_SYSTEM_PROMPT
    assert "Spanish" in JUDGE_SYSTEM_PROMPT


def test_fast_mini_judge_prompt_has_language_policy() -> None:
    assert "Language policy" in FAST_MINI_JUDGE_PROMPT
    assert "Spanish" in FAST_MINI_JUDGE_PROMPT

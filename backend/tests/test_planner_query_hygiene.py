"""Tests for BRD-23 WP-4 query-hygiene planner prompt (AC-10)."""

from __future__ import annotations

from app.llm.prompts import PLANNER_SYSTEM_PROMPT


def test_planner_system_prompt_contains_6_token_clause() -> None:
    assert "6 tokens" in PLANNER_SYSTEM_PROMPT


def test_planner_system_prompt_contains_stopword_rule() -> None:
    assert "stop-words" in PLANNER_SYSTEM_PROMPT
    for stop in ("the", "of", "in", "for"):
        assert f"'{stop}'" in PLANNER_SYSTEM_PROMPT


def test_planner_system_prompt_contains_quoted_phrase_rule() -> None:
    assert "quotes ONLY" in PLANNER_SYSTEM_PROMPT
    assert "exact phrase" in PLANNER_SYSTEM_PROMPT


def test_planner_system_prompt_contains_technical_connectors_exception() -> None:
    for connector in ("'vs'", "'+'", "'-'", "site:"):
        assert connector in PLANNER_SYSTEM_PROMPT
    assert "DO NOT count" in PLANNER_SYSTEM_PROMPT


def test_planner_system_prompt_contains_self_rewrite_instruction() -> None:
    assert "rewrite it once" in PLANNER_SYSTEM_PROMPT

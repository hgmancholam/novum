"""Tests for ``app.agent.states``."""

from __future__ import annotations

import pytest

from app.agent.states import (
    TERMINAL_STATES,
    TRANSITIONS,
    AgentState,
    can_transition,
    is_terminal,
)


def test_can_transition_returns_true_for_every_listed_edge() -> None:
    for src, targets in TRANSITIONS.items():
        for tgt in targets:
            assert can_transition(src, tgt), f"{src} -> {tgt} should be legal"


def test_init_cannot_jump_directly_to_searching() -> None:
    assert can_transition(AgentState.INIT, AgentState.SEARCHING) is False


def test_planning_cannot_jump_to_drafting() -> None:
    assert can_transition(AgentState.PLANNING, AgentState.DRAFTING) is False


def test_is_terminal_true_for_stopped() -> None:
    assert is_terminal(AgentState.STOPPED) is True


def test_is_terminal_true_for_errored() -> None:
    assert is_terminal(AgentState.ERRORED) is True


def test_is_terminal_false_for_planning() -> None:
    assert is_terminal(AgentState.PLANNING) is False


def test_stopped_has_no_outgoing_transitions() -> None:
    assert TRANSITIONS[AgentState.STOPPED] == set()


def test_errored_has_no_outgoing_transitions() -> None:
    assert TRANSITIONS[AgentState.ERRORED] == set()


def test_terminal_states_membership() -> None:
    assert frozenset({AgentState.STOPPED, AgentState.ERRORED}) == TERMINAL_STATES


@pytest.mark.parametrize(
    ("src", "tgt"),
    [
        (AgentState.INIT, AgentState.PLANNING),
        (AgentState.PLANNING, AgentState.CRITIQUING),
        (AgentState.CRITIQUING, AgentState.SEARCHING),
        (AgentState.CRITIQUING, AgentState.REVISING),
        (AgentState.REVISING, AgentState.CRITIQUING),
        (AgentState.SEARCHING, AgentState.ANALYZING),
        (AgentState.ANALYZING, AgentState.SEARCHING),
        (AgentState.ANALYZING, AgentState.DRAFTING),
        (AgentState.DRAFTING, AgentState.JUDGING),
        (AgentState.JUDGING, AgentState.SEARCHING),
        (AgentState.JUDGING, AgentState.STOPPED),
    ],
)
def test_happy_path_edges_are_legal(src: AgentState, tgt: AgentState) -> None:
    assert can_transition(src, tgt) is True

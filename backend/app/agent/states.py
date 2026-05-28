"""Agent FSM states and legal transitions (BRD-07 §4.2)."""

from __future__ import annotations

from enum import StrEnum


class AgentState(StrEnum):
    """States of the research agent FSM."""

    INIT = "init"
    PLANNING = "planning"
    CRITIQUING = "critiquing"
    REVISING = "revising"
    SEARCHING = "searching"
    ANALYZING = "analyzing"
    DRAFTING = "drafting"
    JUDGING = "judging"
    STOPPED = "stopped"
    ERRORED = "errored"


TRANSITIONS: dict[AgentState, set[AgentState]] = {
    # PR-4 Mejora 4.2: INIT → DRAFTING when the classifier flags ambiguity
    # (skip PLANNING/SEARCHING/ANALYZING; BEST_EFFORT synth handles it).
    AgentState.INIT: {
        AgentState.PLANNING,
        AgentState.DRAFTING,
        AgentState.STOPPED,
        AgentState.ERRORED,
    },
    AgentState.PLANNING: {AgentState.CRITIQUING, AgentState.SEARCHING, AgentState.STOPPED, AgentState.ERRORED},
    AgentState.CRITIQUING: {
        AgentState.SEARCHING,
        AgentState.REVISING,
        AgentState.STOPPED,
        AgentState.ERRORED,
    },
    AgentState.REVISING: {AgentState.CRITIQUING, AgentState.STOPPED, AgentState.ERRORED},
    AgentState.SEARCHING: {AgentState.ANALYZING, AgentState.STOPPED, AgentState.ERRORED},
    AgentState.ANALYZING: {
        AgentState.SEARCHING,
        AgentState.DRAFTING,
        AgentState.STOPPED,
        AgentState.ERRORED,
    },
    AgentState.DRAFTING: {AgentState.JUDGING, AgentState.STOPPED, AgentState.ERRORED},
    AgentState.JUDGING: {
        AgentState.SEARCHING,
        AgentState.ANALYZING,  # BRD-23 WP-2: re-analyze after deep-fetch
        AgentState.DRAFTING,
        AgentState.STOPPED,
        AgentState.ERRORED,
    },
    AgentState.STOPPED: set(),
    AgentState.ERRORED: set(),
}


TERMINAL_STATES: frozenset[AgentState] = frozenset({AgentState.STOPPED, AgentState.ERRORED})


def can_transition(from_state: AgentState, to_state: AgentState) -> bool:
    """Return True if ``from_state -> to_state`` is a legal transition."""
    return to_state in TRANSITIONS.get(from_state, set())


def is_terminal(state: AgentState) -> bool:
    """Return True if the state is terminal (no further transitions allowed)."""
    return state in TERMINAL_STATES

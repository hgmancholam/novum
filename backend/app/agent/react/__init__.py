"""ReAct loop package for DEEP lane (IP-25 Phase E).

Implements Thought-Action-Observation loop for abductive reasoning on
causal/scenario questions. Integrates with hypothesis generation from
Phase D and supports dynamic history summarization.
"""

from app.agent.react.actions import (
    AgentActionUnion,
    DeepFetchAction,
    EvaluateHypothesisAction,
    FinishAction,
    SearchAction,
)
from app.agent.react.loop import ReactStep, run_react_loop

__all__ = [
    "AgentActionUnion",
    "DeepFetchAction",
    "EvaluateHypothesisAction",
    "FinishAction",
    "ReactStep",
    "SearchAction",
    "run_react_loop",
]

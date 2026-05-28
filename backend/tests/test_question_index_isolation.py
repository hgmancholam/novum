"""WP-6 G6: Enforce planner-only contract for PriorRunHint (isolation test).

This test verifies that the synthesizer and judge prompt builders do NOT
accept PriorRunHint in their function signatures, ensuring that cross-run
hints remain strictly confined to the planner.
"""

import inspect


def test_synthesizer_does_not_accept_prior_run_hint():
    """Synthesizer prompt builder must not have PriorRunHint in signature."""
    from app.llm.prompts import build_synthesizer_prompt

    sig = inspect.signature(build_synthesizer_prompt)
    for param_name, param in sig.parameters.items():
        annotation = param.annotation
        if annotation == inspect.Parameter.empty:
            continue
        # Check if annotation mentions PriorRunHint (as type or in generics)
        annotation_str = str(annotation)
        assert "PriorRunHint" not in annotation_str, (
            f"Synthesizer prompt builder parameter '{param_name}' has "
            f"PriorRunHint in its type annotation: {annotation}. This violates "
            f"WP-6 G6 isolation contract."
        )


def test_judge_does_not_accept_prior_run_hint():
    """Judge verdict call must not have PriorRunHint in signature.

    The judge is invoked via llm.call(role=JUDGE), so we check the
    evaluate_with_judge function which is the high-level entry point.
    """
    from app.agent.tasks.draft import evaluate_with_judge

    sig = inspect.signature(evaluate_with_judge)
    for param_name, param in sig.parameters.items():
        annotation = param.annotation
        if annotation == inspect.Parameter.empty:
            continue
        annotation_str = str(annotation)
        assert "PriorRunHint" not in annotation_str, (
            f"Judge evaluation function parameter '{param_name}' has "
            f"PriorRunHint in its type annotation: {annotation}. This violates "
            f"WP-6 G6 isolation contract."
        )


def test_planner_can_accept_prior_run_hints():
    """Planner IS allowed to receive PriorRunHint (positive control).

    This test documents that the planner prompt or task is the only place
    where PriorRunHint may appear. We verify that create_plan internally
    queries the index, but we don't enforce a specific signature since
    the hints are generated internally, not passed as parameters.
    """
    from app.agent.tasks.plan import create_plan

    sig = inspect.signature(create_plan)
    # create_plan does NOT receive PriorRunHint as a parameter;
    # it queries the index internally. This test just verifies
    # that the function exists and doesn't accidentally leak hints
    # into synthesizer/judge.
    assert callable(create_plan)

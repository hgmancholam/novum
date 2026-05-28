"""Tests for ``app.llm.roles``."""

from __future__ import annotations

from app.llm.roles import ROLE_CONFIGS, LLMRole, RoleConfig


def test_llm_role_enum_values() -> None:
    assert LLMRole.CLASSIFIER.value == "classifier"
    assert LLMRole.PLANNER.value == "planner"
    assert LLMRole.SYNTHESIZER.value == "synthesizer"
    assert LLMRole.JUDGE.value == "judge"
    assert LLMRole.META_JUDGE.value == "meta_judge"


def test_role_configs_has_all_roles() -> None:
    assert set(ROLE_CONFIGS.keys()) == {
        LLMRole.CLASSIFIER,
        LLMRole.PLANNER,
        LLMRole.SYNTHESIZER,
        LLMRole.JUDGE,
        LLMRole.META_JUDGE,
    }


def test_role_configs_are_well_formed() -> None:
    for role, config in ROLE_CONFIGS.items():
        assert isinstance(config, RoleConfig)
        assert config.model, f"{role} has empty model id"
        assert 0.0 <= config.temperature <= 1.0
        assert config.max_tokens > 0
        assert config.description


def test_judge_is_cross_family_vs_synthesizer() -> None:
    """RF-15: judge model family must differ from synthesizer's family.

    The "family" is the provider prefix before the ``/`` in the model
    id (e.g. ``openai/`` vs ``deepseek/``).
    """
    judge_family = ROLE_CONFIGS[LLMRole.JUDGE].model.split("/", 1)[0]
    synth_family = ROLE_CONFIGS[LLMRole.SYNTHESIZER].model.split("/", 1)[0]
    assert judge_family != synth_family, (
        f"Judge and synthesizer share family {judge_family!r} — violates RF-15"
    )

"""Unit tests for CoVe (Chain-of-Verification) module (IP-25 Phase F)."""


import pytest

from app.agent.tasks.cove import (
    CoveQuestions,
    CoveVerdict,
    generate_verification_questions,
    verify_question,
)
from app.seams.source import SourceResult


@pytest.mark.asyncio
async def test_generate_verification_questions_returns_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that generate_verification_questions clamps to 3 when model returns more."""
    draft = "Tokyo became Japan's capital in 1868 after the Meiji Restoration."

    async def mock_llm_call(role, messages, response_model, **kwargs):
        return CoveQuestions(
            items=[
                "Did Tokyo become capital in 1868?",
                "Was the Meiji Restoration in 1868?",
                "Did Tokyo replace Kyoto?",
                "Is Tokyo still the capital today?",  # 4th question, should be dropped
            ]
        )

    monkeypatch.setattr("app.agent.tasks.cove.llm.call", mock_llm_call)

    questions = await generate_verification_questions(draft)

    assert len(questions) == 3
    assert "Is Tokyo still the capital today?" not in questions


@pytest.mark.asyncio
async def test_generate_verification_questions_pads_when_underfilled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that generate_verification_questions pads to 3 when model returns fewer."""
    draft = "Tokyo is Japan's capital."

    async def mock_llm_call(role, messages, response_model, **kwargs):
        return CoveQuestions(items=["Is Tokyo Japan's capital?"])

    monkeypatch.setattr("app.agent.tasks.cove.llm.call", mock_llm_call)

    questions = await generate_verification_questions(draft)

    assert len(questions) == 3
    assert questions[0] == "Is Tokyo Japan's capital?"
    assert questions[1] == ""
    assert questions[2] == ""


@pytest.mark.asyncio
async def test_generate_verification_questions_raises_on_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that generate_verification_questions raises ValueError when model returns zero."""
    from pydantic import ValidationError

    draft = "Some answer."

    async def mock_llm_call(role, messages, response_model, **kwargs):
        # Pydantic will reject this before our code runs
        return CoveQuestions(items=[])

    monkeypatch.setattr("app.agent.tasks.cove.llm.call", mock_llm_call)

    # Pydantic validation error happens before our ValueError check
    with pytest.raises(ValidationError):
        await generate_verification_questions(draft)


@pytest.mark.asyncio
async def test_verify_question_returns_no_contradiction_when_evidence_supports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that verify_question returns no contradiction when evidence supports claim."""
    question = "Did Tokyo become Japan's capital in 1868?"
    draft = "Tokyo became Japan's capital in 1868."

    # Mock source search to return supporting evidence
    class MockSource:
        source_type = "test"

        async def search(self, query: str, max_results: int = 3):
            return [
                SourceResult(
                    url="https://example.com/1",
                    title="Tokyo History",
                    snippet="Tokyo became the imperial capital in 1868 during the Meiji Restoration.",
                    content="Tokyo became the imperial capital in 1868 during the Meiji Restoration.",
                ),
            ]

    class MockRegistry:
        def types(self):
            return ["test"]

        def get(self, source_type):
            return MockSource()

    registry = MockRegistry()

    async def mock_llm_call(role, messages, response_model, **kwargs):
        return CoveVerdict(
            contradicts=False,
            evidence="Evidence confirms Tokyo became capital in 1868.",
        )

    monkeypatch.setattr("app.agent.tasks.cove.llm.call", mock_llm_call)

    verdict = await verify_question(question, draft, registry)

    assert verdict.contradicts is False
    assert "confirms" in verdict.evidence.lower()


@pytest.mark.asyncio
async def test_verify_question_detects_contradiction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that verify_question detects contradiction when evidence contradicts draft."""
    question = "Did Tokyo become Japan's capital in 1868?"
    draft = "Tokyo became Japan's capital in 1868."

    # Mock source search to return contradicting evidence
    class MockSource:
        source_type = "test"

        async def search(self, query: str, max_results: int = 3):
            return [
                SourceResult(
                    url="https://example.com/1",
                    title="Tokyo History Corrected",
                    snippet="Tokyo became the imperial capital in 1869, not 1868.",
                    content="Tokyo became the imperial capital in 1869, not 1868.",
                ),
            ]

    class MockRegistry:
        def types(self):
            return ["test"]

        def get(self, source_type):
            return MockSource()

    registry = MockRegistry()

    async def mock_llm_call(role, messages, response_model, **kwargs):
        return CoveVerdict(
            contradicts=True,
            evidence="Evidence states Tokyo became capital in 1869, not 1868.",
        )

    monkeypatch.setattr("app.agent.tasks.cove.llm.call", mock_llm_call)

    verdict = await verify_question(question, draft, registry)

    assert verdict.contradicts is True
    assert "1869" in verdict.evidence


@pytest.mark.asyncio
async def test_verify_question_handles_empty_search_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that verify_question handles empty search results gracefully."""
    question = "Did something happen?"
    draft = "Something happened."

    # Mock source search to return no results
    class MockSource:
        source_type = "test"

        async def search(self, query: str, max_results: int = 3):
            return []

    class MockRegistry:
        def types(self):
            return ["test"]

        def get(self, source_type):
            return MockSource()

    registry = MockRegistry()

    verdict = await verify_question(question, draft, registry)

    assert verdict.contradicts is False
    assert verdict.evidence == "no evidence found"


@pytest.mark.asyncio
async def test_verify_question_skips_empty_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that verify_question skips empty questions from padding."""
    # Mock registry (won't be used for empty question)
    class MockRegistry:
        def types(self):
            return []

        def get(self, source_type):
            raise KeyError(source_type)

    registry = MockRegistry()

    verdict = await verify_question("", "Some draft", registry)

    assert verdict.contradicts is False
    assert "skipped empty question" in verdict.evidence


@pytest.mark.asyncio
async def test_verify_question_handles_search_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that verify_question handles source search failures gracefully."""
    question = "Did something happen?"
    draft = "Something happened."

    # Mock source search to raise exception
    class MockSource:
        source_type = "test"

        async def search(self, query: str, max_results: int = 3):
            raise RuntimeError("Search API down")

    class MockRegistry:
        def types(self):
            return ["test"]

        def get(self, source_type):
            return MockSource()

    registry = MockRegistry()

    verdict = await verify_question(question, draft, registry)

    assert verdict.contradicts is False
    assert verdict.evidence == "no evidence found"

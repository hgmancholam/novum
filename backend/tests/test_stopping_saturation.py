"""Tests for novelty-based saturation signal (WP-4)."""

import numpy as np
import pytest

from app.agent.run_state import EvidenceItem, RunState
from app.domain.enums import QuestionType, StopReason
from app.seams.stopping import SignalResult
from app.stopping.signals.saturation import evaluate_saturation
from uuid import uuid4


@pytest.fixture
def mock_state():
    """Create a minimal RunState for saturation testing."""
    return RunState(
        run_id=uuid4(),
        question="Test question",
        question_type=QuestionType.FACTUAL,
        stop_reason=None,
    )


@pytest.mark.asyncio
async def test_saturation_first_round_defers(mock_state, monkeypatch):
    """First round (no prior corpus) returns DEFER."""
    mock_state.search_count = 0  # First round
    mock_state.evidence = [
        EvidenceItem(
            event_id=uuid4(),
            claim_id="c1",
            source_url="http://example.com",
            source_title="Example",
            text="Some evidence text",
            polarity="supports",
            confidence=0.8,
        )
    ]

    async def mock_embed(texts, **kwargs):
        return [np.array([1.0, 0.0, 0.0], dtype=np.float32) for _ in texts]

    monkeypatch.setattr("app.stopping.signals.saturation.embed", mock_embed)

    result = await evaluate_saturation(mock_state)
    assert result.result == SignalResult.DEFER
    assert "First round" in result.explanation


@pytest.mark.asyncio
async def test_saturation_insufficient_chunks_defers(mock_state, monkeypatch):
    """Current round with < k chunks returns DEFER."""
    from app.config import settings

    mock_state.search_count = 1  # Second round
    # Only 2 chunks in current round, need 3
    mock_state.evidence = [
        EvidenceItem(
            event_id=uuid4(),
            claim_id="c1",
            source_url="http://example.com/1",
            source_title="Example 1",
            text="First evidence",
            polarity="supports",
            confidence=0.8,
        ),
        EvidenceItem(
            event_id=uuid4(),
            claim_id="c1",
            source_url="http://example.com/2",
            source_title="Example 2",
            text="Second evidence",
            polarity="supports",
            confidence=0.8,
        ),
    ]

    async def mock_embed(texts, **kwargs):
        return [np.array([1.0, 0.0, 0.0], dtype=np.float32) for _ in texts]

    monkeypatch.setattr("app.stopping.signals.saturation.embed", mock_embed)

    result = await evaluate_saturation(mock_state)
    assert result.result == SignalResult.DEFER
    # Should mention insufficient chunks
    assert "insufficient" in result.explanation.lower() or "need" in result.explanation.lower()


@pytest.mark.asyncio
async def test_saturation_fires_when_novelty_below_threshold(mock_state, monkeypatch):
    """Saturation fires when novelty < NOVELTY_FLOOR."""
    from app.config import settings

    mock_state.search_count = 1  # Second round
    # 6 evidence items: 3 from prior round, 3 from current round
    mock_state.evidence = [
        EvidenceItem(
            event_id=uuid4(),
            claim_id="c1",
            source_url=f"http://example.com/{i}",
            source_title=f"Example {i}",
            text=f"Evidence {i}",
            polarity="supports",
            confidence=0.8,
        )
        for i in range(6)
    ]

    # Mock embeddings: current round chunks are very similar to prior round
    # (high cosine similarity → low novelty)
    def create_mock_embed():
        call_count = [0]

        async def mock_embed(texts, **kwargs):
            embeddings = []
            for _ in texts:
                # First 3 calls: prior corpus (round 1)
                # Last 3 calls: current round (very similar vectors)
                if call_count[0] < 3:
                    embeddings.append(np.array([1.0, 0.0, 0.0], dtype=np.float32))
                else:
                    # Very similar to prior (small perturbation)
                    embeddings.append(np.array([0.99, 0.01, 0.0], dtype=np.float32))
                call_count[0] += 1
            return embeddings

        return mock_embed

    monkeypatch.setattr("app.stopping.signals.saturation.embed", create_mock_embed())

    result = await evaluate_saturation(mock_state)
    assert result.result == SignalResult.DEFER  # Observational, doesn't force stop
    # Check that novelty was computed and is low
    assert mock_state.last_novelty is not None
    assert mock_state.last_novelty < settings.novelty_floor
    assert "saturated" in result.explanation.lower()


@pytest.mark.asyncio
async def test_saturation_continues_when_novelty_above_threshold(mock_state, monkeypatch):
    """Saturation doesn't fire when novelty >= NOVELTY_FLOOR."""
    from app.config import settings

    mock_state.search_count = 1  # Second round
    mock_state.evidence = [
        EvidenceItem(
            event_id=uuid4(),
            claim_id="c1",
            source_url=f"http://example.com/{i}",
            source_title=f"Example {i}",
            text=f"Evidence {i}",
            polarity="supports",
            confidence=0.8,
        )
        for i in range(6)
    ]

    # Mock embeddings: current round chunks are very different from prior
    # (low cosine similarity → high novelty)
    def create_mock_embed():
        call_count = [0]

        async def mock_embed(texts, **kwargs):
            embeddings = []
            for _ in texts:
                if call_count[0] < 3:
                    # Prior corpus
                    embeddings.append(np.array([1.0, 0.0, 0.0], dtype=np.float32))
                else:
                    # Current round: orthogonal vectors (zero cosine similarity)
                    embeddings.append(np.array([0.0, 1.0, 0.0], dtype=np.float32))
                call_count[0] += 1
            return embeddings

        return mock_embed

    monkeypatch.setattr("app.stopping.signals.saturation.embed", create_mock_embed())

    result = await evaluate_saturation(mock_state)
    assert result.result == SignalResult.DEFER
    assert mock_state.last_novelty is not None
    assert mock_state.last_novelty >= settings.novelty_floor
    assert "continuing" in result.explanation.lower()

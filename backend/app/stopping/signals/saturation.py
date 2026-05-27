"""Novelty-based saturation signal (WP-4 G1).

Computes novelty as: 1 - mean(max_cosine_similarity(chunk_i, prior_corpus))
over the last k=3 retrieved chunks from the current evidence round.

When novelty < NOVELTY_FLOOR, the signal fires and emits
SaturationDetectedEvent. The signal is observational only — it informs
the judge via the draft context but does NOT directly force a stop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import structlog

from app.config import settings
from app.llm.embeddings import embed
from app.seams.stopping import SignalResult, StopSignalOutput

if TYPE_CHECKING:
    from app.agent.run_state import RunState

logger = structlog.get_logger()


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    if a.size == 0 or b.size == 0:
        return 0.0
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


async def evaluate_saturation(state: RunState) -> StopSignalOutput:
    """Evaluate if evidence collection has saturated (novelty < threshold).

    Algorithm (G1):
    - chunk = one EvidenceAddedEvent payload (the text of one evidence item)
    - prior_corpus = all chunks from rounds 1..r-1 (excludes current round)
    - last_k_chunks = most recent SATURATION_WINDOW chunks from current round
    - For each chunk_i in last_k_chunks, compute max cosine similarity with
      all vectors in prior_corpus
    - novelty = 1 - mean(max_similarities)
    - Fire when novelty < NOVELTY_FLOOR

    Special cases:
    - First round (no prior corpus) → defer (novelty undefined)
    - Fewer than k chunks in current round → defer (insufficient data)
    """
    k = settings.saturation_window
    threshold = settings.novelty_floor

    # Count evidence by round (we increment search_count after each round)
    current_round = state.search_count + 1

    if current_round == 1:
        # First round: no prior corpus to compare against
        logger.debug("saturation_skip_first_round", round=current_round)
        return StopSignalOutput(
            signal_name="saturation",
            result=SignalResult.DEFER,
            explanation="First round — no prior corpus for novelty comparison",
        )

    # Partition evidence by round (using event order as proxy for round assignment)
    # We'll embed new chunks that don't have embeddings yet
    current_round_chunks = []
    prior_round_chunks = []

    for i, evidence in enumerate(state.evidence):
        event_id = str(evidence.event_id)
        text = evidence.text

        # Embed if not cached
        if event_id not in state.chunk_embeddings:
            try:
                vecs = await embed([text])
                state.chunk_embeddings[event_id] = vecs[0]
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "saturation_embed_failed",
                    event_id=event_id,
                    error=str(exc),
                )
                continue

        # Heuristic: evidence items from the last ~k items belong to current round
        # This is approximate since we don't track round explicitly per evidence
        # For V1, we treat the last len(state.evidence) // current_round items as current
        items_per_round = max(1, len(state.evidence) // max(1, current_round))
        if i >= len(state.evidence) - items_per_round:
            current_round_chunks.append(state.chunk_embeddings[event_id])
        else:
            prior_round_chunks.append(state.chunk_embeddings[event_id])

    if len(current_round_chunks) < k:
        logger.debug(
            "saturation_insufficient_chunks",
            current_chunks=len(current_round_chunks),
            required=k,
        )
        return StopSignalOutput(
            signal_name="saturation",
            result=SignalResult.DEFER,
            explanation=f"Current round has {len(current_round_chunks)} chunks, need {k}",
        )

    if not prior_round_chunks:
        # Defensive: should not happen if current_round > 1, but guard anyway
        logger.debug("saturation_no_prior_corpus", round=current_round)
        return StopSignalOutput(
            signal_name="saturation",
            result=SignalResult.DEFER,
            explanation="No prior corpus available",
        )

    # Compute novelty: for each of the last k chunks, find max similarity with prior corpus
    last_k = current_round_chunks[-k:]
    max_similarities = []

    for chunk_vec in last_k:
        similarities = [_cosine_similarity(chunk_vec, prior_vec) for prior_vec in prior_round_chunks]
        max_sim = max(similarities) if similarities else 0.0
        max_similarities.append(max_sim)

    novelty = 1.0 - (sum(max_similarities) / len(max_similarities))
    state.last_novelty = novelty

    logger.info(
        "saturation_computed",
        round=current_round,
        novelty=novelty,
        threshold=threshold,
        k=k,
        fired=novelty < threshold,
    )

    if novelty < threshold:
        return StopSignalOutput(
            signal_name="saturation",
            result=SignalResult.DEFER,  # observational only, doesn't force stop
            explanation=f"Novelty {novelty:.3f} < {threshold} (saturated)",
        )

    return StopSignalOutput(
        signal_name="saturation",
        result=SignalResult.DEFER,
        explanation=f"Novelty {novelty:.3f} >= {threshold} (continuing)",
    )

"""Cross-run question memory (WP-6).

In-memory LRU index of prior run questions with their embeddings and
sub-claims. Used by the planner to borrow relevant sub-claims from
similar past questions.

Hard contract (G6): The index returns ``PriorRunHint`` which is
deliberately missing ``answer_kind``, ``prose``, ``key_points``,
``citations``, ``confidence``, and ``judge_verdict``. The planner sees
hints; the synthesizer and judge never do.
"""

from __future__ import annotations

from collections import OrderedDict
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict

from app.config import settings


class PriorRunHint(BaseModel):
    """What the planner is allowed to see from past runs (WP-6 G6).

    DELIBERATELY ABSENT: answer_kind, prose, key_points, citations,
    confidence, judge_verdict. Adding any of them is a contract violation.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    question_text: str
    sub_claims: list[str]


class QuestionEmbeddingIndex:
    """LRU index of prior run questions with embeddings.

    Process-local singleton. Cap at PRIOR_RUN_INDEX_CAP (default 256)
    entries. Oldest entries evicted first when cap is reached.
    """

    def __init__(self, cap: int | None = None) -> None:
        self._cap = cap or settings.prior_run_index_cap
        # OrderedDict: insertion order preserved, move_to_end() for LRU
        # Key: run_id, Value: (question_text, embedding_vec, sub_claims)
        self._store: OrderedDict[UUID, tuple[str, np.ndarray, list[str]]] = OrderedDict()

    def add(
        self,
        run_id: UUID,
        question: str,
        vec: np.ndarray,
        sub_claims: list[str],
    ) -> None:
        """Add or update a question entry.

        If the index is at capacity, the oldest entry is evicted (FIFO/LRU).
        """
        if run_id in self._store:
            # Update existing: move to end (most recent)
            del self._store[run_id]

        self._store[run_id] = (question, vec, sub_claims)

        # Evict oldest if over cap
        if len(self._store) > self._cap:
            self._store.popitem(last=False)  # Remove oldest (FIFO)

    def top_k(self, vec: np.ndarray, k: int = 3) -> list[PriorRunHint]:
        """Return top-k most similar prior runs by cosine similarity.

        Marks accessed entries as recently used (moves to end for LRU).
        """
        if not self._store or vec.size == 0:
            return []

        # Compute similarities for all stored questions
        similarities: list[tuple[float, UUID, str, list[str]]] = []
        for run_id, (question, stored_vec, sub_claims) in self._store.items():
            sim = self._cosine_similarity(vec, stored_vec)
            similarities.append((sim, run_id, question, sub_claims))

        # Sort by similarity descending
        similarities.sort(reverse=True, key=lambda x: x[0])

        # Take top-k
        top = similarities[:k]

        # Mark as accessed (move to end for LRU)
        for _, run_id, _, _ in top:
            self._store.move_to_end(run_id)

        return [
            PriorRunHint(run_id=run_id, question_text=question, sub_claims=sub_claims)
            for _, run_id, question, sub_claims in top
        ]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        if a.size == 0 or b.size == 0:
            return 0.0
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    def clear(self) -> None:
        """Clear all entries (used in tests and shutdown)."""
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


# Global singleton instance (instantiated in main.py lifespan)
_index: QuestionEmbeddingIndex | None = None


def get_index() -> QuestionEmbeddingIndex:
    """Get the global question index singleton."""
    global _index
    if _index is None:
        _index = QuestionEmbeddingIndex()
    return _index


def reset_index() -> None:
    """Reset the global index (for tests and shutdown)."""
    global _index
    if _index:
        _index.clear()
    _index = None

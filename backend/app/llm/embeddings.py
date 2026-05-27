"""Embedding utilities via litellm hosted endpoints (WP-4).

Provides ``embed()`` for converting texts into vector representations
using OpenAI's text-embedding-3-small model through litellm. Used by
the saturation signal to compute novelty.

No sentence-transformers or local model dependencies (M1) — all
embeddings are served via GitHub Models / OpenAI-compatible endpoints.
"""

from __future__ import annotations

import numpy as np
import structlog
from litellm import aembedding

from app.config import settings

logger = structlog.get_logger()


async def embed(
    texts: list[str],
    *,
    model: str | None = None,
) -> list[np.ndarray]:
    """Embed multiple texts using the configured embedding model.

    Args:
        texts: List of text strings to embed
        model: Optional model override (defaults to settings.EMBEDDING_MODEL)

    Returns:
        List of numpy arrays, one per input text. Each array has shape (dim,)
        where dim is the model's embedding dimension (1536 for text-embedding-3-small).

    Raises:
        Exception: Propagates litellm errors (auth, rate limit, etc.)
    """
    if not texts:
        return []

    model_id = model or settings.EMBEDDING_MODEL

    logger.info(
        "embedding_start",
        model=model_id,
        num_texts=len(texts),
    )

    # litellm.aembedding returns a response object with .data = list[dict]
    # where each dict has {"embedding": list[float], "index": int, ...}
    response = await aembedding(
        model=model_id,
        input=texts,
        api_key=settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None,
    )

    embeddings = [np.array(item["embedding"], dtype=np.float32) for item in response.data]

    logger.info(
        "embedding_complete",
        model=model_id,
        num_texts=len(texts),
        dim=len(embeddings[0]) if embeddings else 0,
    )

    return embeddings

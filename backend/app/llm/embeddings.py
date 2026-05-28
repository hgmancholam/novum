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
from litellm.exceptions import AuthenticationError, RateLimitError

from app.config import settings
from app.llm.client import _TOKEN_POOL, _call_with_token_fallback

logger = structlog.get_logger()


async def embed(
    texts: list[str],
    *,
    model: str | None = None,
) -> list[np.ndarray]:
    """Embed multiple texts using the configured embedding model.

    Args:
        texts: List of text strings to embed
        model: Optional model override (defaults to settings.embedding_model)

    Returns:
        List of numpy arrays, one per input text. Each array has shape (dim,)
        where dim is the model's embedding dimension (1536 for text-embedding-3-small).

    Raises:
        Exception: Propagates litellm errors (auth, rate limit, etc.)
    """
    if not texts:
        return []

    model_id = model or settings.embedding_model

    logger.info(
        "embedding_start",
        model=model_id,
        num_texts=len(texts),
    )

    async def _via_github_pool():
        async def _do(token: str):
            return await aembedding(
                model=model_id,
                input=texts,
                api_base=settings.llm_api_base,
                api_key=token,
            )

        if _TOKEN_POOL:
            return await _call_with_token_fallback(_do)
        return await _do(settings.github_token)

    # Prefer dedicated OpenAI key when present; on quota/auth failures
    # fall back to the GitHub Models endpoint (which also serves
    # ``openai/text-embedding-3-small`` against the PAT pool) so a dead
    # OpenAI quota never blocks the saturation signal.
    if settings.openai_api_key:
        try:
            response = await aembedding(
                model=model_id,
                input=texts,
                api_key=settings.openai_api_key.get_secret_value(),
            )
        except (RateLimitError, AuthenticationError) as exc:
            logger.warning(
                "embedding_openai_fallback_to_github",
                model=model_id,
                error=str(exc),
            )
            response = await _via_github_pool()
    else:
        response = await _via_github_pool()

    embeddings = [np.array(item["embedding"], dtype=np.float32) for item in response.data]

    logger.info(
        "embedding_complete",
        model=model_id,
        num_texts=len(texts),
        dim=len(embeddings[0]) if embeddings else 0,
    )

    return embeddings

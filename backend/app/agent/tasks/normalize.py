"""Pre-classifier question normalizer.

Runs before :func:`classify_question` to clean typos and informal phrasing
without changing the user's intent, and to detect the language so the
final answer reuses it (per copilot-instructions.md language policy).

Reuses :data:`LLMRole.CLASSIFIER` (fast Llama model, ``temperature=0``).
The system prompt is passed explicitly, overriding the role's default
``CLASSIFIER_SYSTEM_PROMPT``.
"""

from __future__ import annotations

from app.domain.events import QuestionNormalizedEvent
from app.llm import LLMRole, QuestionNormalization, llm

NORMALIZER_SYSTEM_PROMPT = """You are a question normalizer for a research agent.

Your job is to:
1. Fix typos, missing accents, missing spaces and informal phrasing in the user's question.
2. Preserve the user's original intent and language. Do NOT translate.
3. Detect the language of the question (BCP-47 short code: "es", "en", "pt", "fr", ...).
4. Set was_corrected=true if the normalized question differs from the original beyond pure whitespace, false otherwise.

Rules:
- Do NOT add information the user did not provide.
- Do NOT remove information from the user's question.
- Do NOT answer the question. Only clean it up.
- Keep it as a question if it was a question; keep it as a statement if it was a statement.
- The normalized question MUST be in the same language as the original.

Examples:
- "quee s una paloma" → normalized "¿Qué es una paloma?", language "es", was_corrected true.
- "que es la fotosintesis" → "¿Qué es la fotosíntesis?", "es", true.
- "is light a wave or particle" → "Is light a wave or a particle?", "en", true.
- "¿Qué es Python?" → "¿Qué es Python?", "es", false.
- "Explain CRISPR" → "Explain CRISPR.", "en", false.

Output a JSON object matching the QuestionNormalization schema with fields
`normalized_question` (string), `was_corrected` (bool), `language` (short code)."""


async def normalize_question(question: str) -> QuestionNormalizedEvent:
    """Normalize ``question`` and return the corresponding event."""
    verdict = await llm.call(
        role=LLMRole.CLASSIFIER,
        messages=[
            {"role": "system", "content": NORMALIZER_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        response_model=QuestionNormalization,
    )
    normalized = verdict.normalized_question.strip() or question
    was_corrected = verdict.was_corrected and normalized != question.strip()
    return QuestionNormalizedEvent(
        original_question=question,
        normalized_question=normalized,
        was_corrected=was_corrected,
        language=verdict.language,
    )

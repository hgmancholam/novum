"""Complexity hint derivation for planning budget (BRD-22).

Deterministic heuristic that classifies questions as trivial / standard / deep
based on word count, question type, classifier confidence, and entity count.

This module powers Task 3.1, 3.2 of IP-22.
"""

from typing import Any

from app.config import settings
from app.domain.enums import ComplexityHint, QuestionType


def _count_named_entities(question: str) -> int:
    """Count contiguous runs of capitalised tokens in the question.

    Heuristic: split on whitespace, strip leading sentence interrogatives,
    count contiguous runs of title-case or ALL-CAPS tokens. A contiguous run
    is one or more adjacent tokens matching `tok[0].isupper() and (tok[1:].islower() or tok.isupper())`.

    Hyphenated entities (e.g. "Hewlett-Packard") count as 1 token (no split on hyphen).
    Each contiguous run = 1 entity; non-contiguous runs separated by lowercase tokens
    (e.g. `vs`, `and`) count separately.

    Examples (from Task 3.2):
    - "Tokyo" → 1
    - "Event Sourcing" → 1 (contiguous)
    - "PostgreSQL vs MongoDB" → 2 (non-contiguous, separated by `vs`)
    - "What is CQRS?" → 1
    - "Hewlett-Packard" → 1
    - "Event Sourcing and CQRS" → 2

    Args:
        question: The user's question string.

    Returns:
        Number of distinct named-entity runs detected.
    """
    # Sentence-initial interrogatives to strip (case-insensitive)
    interrogatives = {
        "what", "why", "where", "when", "who", "how",
        "is", "are", "do", "does", "did", "can", "could", "would", "should"
    }

    # Split on whitespace
    tokens = question.split()

    # Strip leading interrogatives (only at position 0)
    if tokens and tokens[0].lower() in interrogatives:
        tokens = tokens[1:]

    # Strip trailing punctuation from each token before case test
    def strip_punct(tok: str) -> str:
        return tok.rstrip("?!.,;:")

    # Strip sentence-initial non-entity capitalization: if first token is title-case  # (not all-caps) and followed by lowercase connector words (of, in, for, etc.),
    # it's likely sentence-initial, not a proper noun
    common_connectors = {"of", "in", "for", "on", "at", "to", "by", "from", "with"}
    if len(tokens) > 1 and tokens[0] and tokens[0][0].isupper() and not tokens[0].isupper():
        second_tok = strip_punct(tokens[1]).lower()
        # If second token is a common connector, skip first token
        if second_tok in common_connectors:
            tokens = tokens[1:]

    # Entity test: token starts with uppercase AND (rest is lowercase OR all uppercase)
    def is_entity_token(tok: str) -> bool:
        tok = strip_punct(tok)
        if not tok or not tok[0].isupper():
            return False
        return tok[1:].islower() or tok.isupper()

    # Count contiguous runs
    entity_runs = 0
    in_run = False
    for token in tokens:
        if is_entity_token(token):
            if not in_run:
                entity_runs += 1
                in_run = True
        else:
            in_run = False

    return entity_runs


def derive_complexity_hint(
    question: str,
    question_type: QuestionType,
    classifier_confidence: float | None,
) -> tuple[ComplexityHint, dict[str, Any]]:
    """Derive complexity hint using deterministic heuristic (BRD-22 §4.5).

    Heuristic rules:
    - `trivial` ⟺ (len(words) ≤ max_trivial_words) AND
                  question_type ∈ {FACTUAL, DEFINITIONAL} AND
                  classifier_confidence ≥ min_trivial_confidence AND
                  single_named_entity_detected
    - `deep` ⟺ question_type ∈ {STATE_OF_ART, CAUSAL, COMPARATIVE} AND
               (len(words) ≥ min_deep_words OR classifier_confidence < max_deep_confidence)
    - `standard` ⟺ otherwise

    Args:
        question: The user's question.
        question_type: Question type from the classifier.
        classifier_confidence: Classifier's self-reported confidence (0..1).
                               If None, defaults to 1.0 (back-compat).

    Returns:
        (complexity_hint, signals_dict) where signals_dict contains:
        - word_count: int
        - entity_count: int
        - single_entity: bool
        - confidence_floor_met: bool (classifier_confidence >= min_trivial_confidence)
    """
    # Use fallback confidence when missing
    conf = classifier_confidence if classifier_confidence is not None else 1.0

    # Word count (simple whitespace split)
    word_count = len(question.split())

    # Entity count
    entity_count = _count_named_entities(question)
    single_entity = entity_count == 1

    # Confidence floor for trivial
    confidence_floor_met = conf >= settings.complexity_min_trivial_confidence

    # Signals dict
    signals = {
        "word_count": word_count,
        "entity_count": entity_count,
        "single_entity": single_entity,
        "confidence_floor_met": confidence_floor_met,
    }

    # Trivial check
    if (
        word_count <= settings.complexity_max_trivial_words
        and question_type in {QuestionType.FACTUAL, QuestionType.DEFINITIONAL}
        and confidence_floor_met
        and single_entity
    ):
        return ComplexityHint.TRIVIAL, signals

    # Deep check
    if question_type in {QuestionType.STATE_OF_ART, QuestionType.CAUSAL, QuestionType.COMPARATIVE}:
        if word_count >= settings.complexity_min_deep_words or conf < settings.complexity_max_deep_confidence:
            return ComplexityHint.DEEP, signals

    # Standard fallback
    return ComplexityHint.STANDARD, signals

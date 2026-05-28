"""AC-09 (BRD-23 WP-2): pre-WP-2 traces must replay cleanly.

This verifies the deep-fetch additions are additive only:
* A persisted trace with no ``DeepFetchPerformed`` events folds without error.
* ``EventType.DEEP_FETCH_PERFORMED`` is registered in ``EVENT_TYPE_MAP``.
* ``DeepFetchPerformedEvent`` validation tolerates the documented optional
  ``failure_reason`` shape (success path omits it).
"""

from __future__ import annotations

from app.domain.enums import EventType, SourceType
from app.domain.events import (
    EVENT_TYPE_MAP,
    DeepFetchPerformedEvent,
    Event,
    QuestionAskedEvent,
)
from pydantic import TypeAdapter


_EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)


def test_pre_wp2_trace_replays_without_deep_fetch_events() -> None:
    """A persisted JSONL line predating WP-2 must validate via the union."""
    legacy_line = {
        "type": "QuestionAsked",
        "question": "what is event sourcing?",
    }
    ev = _EVENT_ADAPTER.validate_python(legacy_line)
    assert isinstance(ev, QuestionAskedEvent)


def test_deep_fetch_event_type_is_registered() -> None:
    assert EventType.DEEP_FETCH_PERFORMED.value == "DeepFetchPerformed"
    assert EVENT_TYPE_MAP["DeepFetchPerformed"] is DeepFetchPerformedEvent


def test_deep_fetch_event_success_payload_round_trips() -> None:
    payload = {
        "type": "DeepFetchPerformed",
        "source_type": "tavily",
        "url": "https://example.com/article",
        "triggered_by_claim_id": "c1",
        "fetch_ms": 812,
        "content_length": 4123,
        "success": True,
    }
    ev = _EVENT_ADAPTER.validate_python(payload)
    assert isinstance(ev, DeepFetchPerformedEvent)
    assert ev.success is True
    assert ev.failure_reason is None
    assert ev.source_type is SourceType.TAVILY


def test_deep_fetch_event_failure_payload_round_trips() -> None:
    payload = {
        "type": "DeepFetchPerformed",
        "source_type": "wikipedia",
        "url": "https://en.wikipedia.org/wiki/X",
        "triggered_by_claim_id": "c2",
        "fetch_ms": 0,
        "content_length": 0,
        "success": False,
        "failure_reason": "Timeout",
    }
    ev = _EVENT_ADAPTER.validate_python(payload)
    assert isinstance(ev, DeepFetchPerformedEvent)
    assert ev.success is False
    assert ev.failure_reason == "Timeout"
    assert ev.source_type is SourceType.WIKIPEDIA

"""Event persistence and retrieval (append-only per RF-03)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.events import BaseEvent
from app.models import Event

# Keys that live on the envelope, not inside the JSONB payload.
_ENVELOPE_KEYS: frozenset[str] = frozenset(
    {"id", "run_id", "step_index", "parent_event_id", "created_at"}
)


class EventService:
    """Service for event operations (BRD-03 §4.6).

    Events are append-only — there are no update or delete paths.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def append_event(
        self,
        run_id: UUID,
        event: BaseEvent,
        parent_event_id: UUID | None = None,
        *,
        commit: bool = True,
    ) -> Event:
        """Append an event to a run's event log.

        Computes the next `step_index` as `max(step_index) + 1` for the
        run (or 1 if no prior events).

        When ``commit=False`` the caller is responsible for committing
        the surrounding transaction — only ``flush()`` + ``refresh()`` run
        here. This lets a single transaction bundle an event append with
        a row mutation (e.g. ``RunService.resume_run`` clearing
        ``stop_reason`` atomically with the ``ResumedAfter*`` event).
        """
        query = (
            select(Event.step_index)
            .where(Event.run_id == run_id)
            .order_by(Event.step_index.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        last_index = result.scalar()
        next_index = (last_index or 0) + 1

        payload = event.model_dump(mode="json", exclude=set(_ENVELOPE_KEYS))
        event_type = payload.get("type") or getattr(event, "type", None)
        db_event = Event(
            run_id=run_id,
            step_index=next_index,
            parent_event_id=parent_event_id,
            type=event_type,
            payload=payload,
        )
        self.db.add(db_event)
        if commit:
            await self.db.commit()
            await self.db.refresh(db_event)
        else:
            await self.db.flush()
            await self.db.refresh(db_event)
        return db_event

    async def get_events(
        self,
        run_id: UUID,
        after_step: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get events for a run, optionally after a step index.

        Returns the SSE-shaped dict (envelope merged with payload).
        """
        query = (
            select(Event)
            .where(Event.run_id == run_id)
            .where(Event.step_index > after_step)
            .order_by(Event.step_index)
            .limit(limit)
        )
        result = await self.db.execute(query)
        events = result.scalars().all()

        return [
            {
                "id": str(e.id),
                "run_id": str(e.run_id),
                "step_index": e.step_index,
                "parent_event_id": (
                    str(e.parent_event_id) if e.parent_event_id else None
                ),
                "type": e.type,
                "created_at": e.created_at.isoformat(),
                **e.payload,
            }
            for e in events
        ]

    async def get_event(self, event_id: UUID) -> Event | None:
        """Get a single event by ID."""
        return await self.db.get(Event, event_id)

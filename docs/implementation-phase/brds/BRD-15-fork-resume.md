# BRD-15: Fork & Resume from Events

**Document ID:** BRD-15
**Version:** 1.0
**Status:** Implemented (CR-15-001 — 9.73/10, 2026-05-26) · reconciliation v1.1 owed (see D-029/D-031)
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 16 of 19

---

## 1. Executive Summary

Implement fork and resume capabilities per RF-03. Users can fork a run from any forkable event to explore alternative research paths, or resume a stopped run. Events are never deleted—only appended.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-03 | Fork/resume from events | Complete |
| RF-04 | Events never deleted | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-02, BRD-07, BRD-14 | Complete |

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    services/
      fork_service.py       # Fork/resume logic
    routes/
      runs.py               # Updated with fork/resume endpoints
frontend/
  src/
    components/
      organisms/
        ForkModal.tsx       # Fork point selection
    lib/
      api.ts                # Updated with fork/resume functions
```

### 4.2 Forkable Events

Events that can serve as fork points (from domain models):

```python
FORKABLE_EVENTS = {
    "PlanCreated",
    "EvidenceCollected",
    "ContradictionDetected",
    "AnswerDrafted",
    "JudgeVerdict",
}
```

### 4.3 Fork Service

#### backend/app/services/fork_service.py

```python
"""Fork and resume service — RF-03."""

from uuid import UUID, uuid4
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.orm import Run, Event
from app.domain.events import ForkCreated, ResumeStarted, Event as DomainEvent
from app.domain.enums import RunStatus

logger = structlog.get_logger()


class ForkService:
    """Handles fork and resume operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def fork_run(
        self,
        original_run_id: UUID,
        fork_at_step: int,
        user_id: UUID,
    ) -> Run:
        """Fork a run from a specific event.
        
        Creates a new run with:
        1. Same question as original
        2. Copied events up to fork_at_step
        3. New ForkCreated event
        
        Original run is NOT modified (RF-04).
        
        Args:
            original_run_id: Run to fork from
            fork_at_step: Step index to fork from
            user_id: User creating the fork
            
        Returns:
            New Run instance
        """
        # Fetch original run
        original = await self.db.get(Run, original_run_id)
        if not original:
            raise ValueError(f"Run {original_run_id} not found")

        # Validate fork point
        fork_event = await self._get_event_at_step(original_run_id, fork_at_step)
        if not fork_event:
            raise ValueError(f"No event at step {fork_at_step}")

        if fork_event.type not in FORKABLE_EVENTS:
            raise ValueError(
                f"Event type {fork_event.type} is not forkable. "
                f"Valid types: {FORKABLE_EVENTS}"
            )

        # Create new run
        new_run_id = uuid4()
        new_run = Run(
            id=new_run_id,
            user_id=user_id,
            question=original.question,
            status=RunStatus.RUNNING,
            forked_from_id=original_run_id,
            forked_at_step=fork_at_step,
            threshold=original.threshold,
            max_searches=original.max_searches,
            created_at=datetime.utcnow(),
        )
        self.db.add(new_run)

        # Copy events up to fork point
        events_to_copy = await self._get_events_up_to(original_run_id, fork_at_step)
        for i, event in enumerate(events_to_copy):
            new_event = Event(
                run_id=new_run_id,
                step_index=i,
                type=event.type,
                payload=event.payload,
                created_at=datetime.utcnow(),
            )
            self.db.add(new_event)

        # Add ForkCreated event
        fork_event = Event(
            run_id=new_run_id,
            step_index=len(events_to_copy),
            type="ForkCreated",
            payload={
                "forked_from_run_id": str(original_run_id),
                "forked_at_step": fork_at_step,
                "timestamp": datetime.utcnow().isoformat(),
            },
            created_at=datetime.utcnow(),
        )
        self.db.add(fork_event)

        await self.db.commit()
        await self.db.refresh(new_run)

        logger.info(
            "run_forked",
            original_run_id=str(original_run_id),
            new_run_id=str(new_run_id),
            fork_at_step=fork_at_step,
        )

        return new_run

    async def resume_run(
        self,
        run_id: UUID,
        user_id: UUID,
    ) -> Run:
        """Resume a stopped run.
        
        Adds a ResumeStarted event and sets status back to RUNNING.
        Original events are preserved (RF-04).
        
        Args:
            run_id: Run to resume
            user_id: User requesting resume
            
        Returns:
            Updated Run instance
        """
        run = await self.db.get(Run, run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        if run.status == RunStatus.RUNNING:
            raise ValueError("Run is already running")

        # Get current event count
        result = await self.db.execute(
            select(Event)
            .where(Event.run_id == run_id)
            .order_by(Event.step_index.desc())
            .limit(1)
        )
        last_event = result.scalar_one_or_none()
        next_step = (last_event.step_index + 1) if last_event else 0

        # Add ResumeStarted event
        resume_event = Event(
            run_id=run_id,
            step_index=next_step,
            type="ResumeStarted",
            payload={
                "resumed_by": str(user_id),
                "timestamp": datetime.utcnow().isoformat(),
            },
            created_at=datetime.utcnow(),
        )
        self.db.add(resume_event)

        # Update run status
        run.status = RunStatus.RUNNING
        run.stop_reason = None
        run.completed_at = None

        await self.db.commit()
        await self.db.refresh(run)

        logger.info("run_resumed", run_id=str(run_id))

        return run

    async def _get_event_at_step(
        self, run_id: UUID, step_index: int
    ) -> Event | None:
        """Get event at specific step index."""
        result = await self.db.execute(
            select(Event).where(
                Event.run_id == run_id,
                Event.step_index == step_index,
            )
        )
        return result.scalar_one_or_none()

    async def _get_events_up_to(
        self, run_id: UUID, step_index: int
    ) -> list[Event]:
        """Get all events up to and including step_index."""
        result = await self.db.execute(
            select(Event)
            .where(Event.run_id == run_id, Event.step_index <= step_index)
            .order_by(Event.step_index)
        )
        return list(result.scalars().all())


# FORKABLE_EVENTS constant
FORKABLE_EVENTS = {
    "PlanCreated",
    "EvidenceCollected",
    "ContradictionDetected",
    "AnswerDrafted",
    "JudgeVerdict",
}
```

### 4.4 API Endpoints

#### backend/app/routes/runs.py (additions)

```python
# ... existing imports ...
from app.services.fork_service import ForkService


class ForkRequest(BaseModel):
    """Request to fork a run."""

    step_index: int


class ResumeRequest(BaseModel):
    """Request to resume a run."""

    pass  # No body needed


@router.post("/{run_id}/fork", response_model=RunResponse)
async def fork_run(
    run_id: UUID,
    request: ForkRequest,
    db: DbSession,
    user: CurrentUser,
) -> RunResponse:
    """Fork a run from a specific event (RF-03).
    
    Creates a new run branching from the specified step_index.
    The original run is not modified.
    """
    fork_service = ForkService(db)
    new_run = await fork_service.fork_run(
        original_run_id=run_id,
        fork_at_step=request.step_index,
        user_id=user.id,
    )
    return RunResponse.from_orm(new_run)


@router.post("/{run_id}/resume", response_model=RunResponse)
async def resume_run(
    run_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> RunResponse:
    """Resume a stopped run (RF-03).
    
    Adds a ResumeStarted event and restarts the agent.
    """
    fork_service = ForkService(db)
    run = await fork_service.resume_run(
        run_id=run_id,
        user_id=user.id,
    )
    # TODO: Trigger agent restart via task queue
    return RunResponse.from_orm(run)
```

### 4.5 API Client Updates

#### frontend/src/lib/api.ts (additions)

```typescript
// ... existing code ...

export async function forkRun(
  runId: string,
  stepIndex: number
): Promise<{ id: string }> {
  const response = await fetch(`${API_URL}/api/runs/${runId}/fork`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ step_index: stepIndex }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to fork run");
  }

  return response.json();
}

export async function resumeRun(runId: string): Promise<{ id: string }> {
  const response = await fetch(`${API_URL}/api/runs/${runId}/resume`, {
    method: "POST",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to resume run");
  }

  return response.json();
}
```

### 4.6 Fork Modal Component

#### frontend/src/components/organisms/ForkModal.tsx

```typescript
/**
 * Modal for selecting fork point.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Button, Spinner } from "@/components/atoms";
import { forkRun } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { RunEvent } from "@/types/events";

const FORKABLE_TYPES = [
  "PlanCreated",
  "EvidenceCollected",
  "ContradictionDetected",
  "AnswerDrafted",
  "JudgeVerdict",
];

interface ForkModalProps {
  runId: string;
  events: RunEvent[];
  onClose: () => void;
}

export function ForkModal({ runId, events, onClose }: ForkModalProps) {
  const navigate = useNavigate();
  const [selectedStep, setSelectedStep] = useState<number | null>(null);

  const forkableEvents = events
    .map((event, index) => ({ event, index }))
    .filter(({ event }) => FORKABLE_TYPES.includes(event.type));

  const mutation = useMutation({
    mutationFn: (stepIndex: number) => forkRun(runId, stepIndex),
    onSuccess: (data) => {
      onClose();
      navigate(`/research/${data.id}`);
    },
  });

  const handleFork = () => {
    if (selectedStep !== null) {
      mutation.mutate(selectedStep);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-xl font-semibold">Fork Run</h2>
        <p className="mb-4 text-sm text-gray-600">
          Select an event to fork from. A new run will be created starting from
          this point.
        </p>

        {/* Event list */}
        <div className="mb-4 max-h-64 overflow-y-auto rounded-lg border border-gray-200">
          {forkableEvents.length === 0 ? (
            <p className="p-4 text-center text-gray-500">
              No forkable events in this run
            </p>
          ) : (
            forkableEvents.map(({ event, index }) => (
              <button
                key={index}
                onClick={() => setSelectedStep(index)}
                className={cn(
                  "flex w-full items-center gap-3 border-b border-gray-100 p-3 text-left hover:bg-gray-50",
                  selectedStep === index && "bg-blue-50"
                )}
              >
                <span className="text-sm font-medium">#{index + 1}</span>
                <span className="flex-1 text-sm">{event.type}</span>
                {selectedStep === index && (
                  <svg
                    className="h-5 w-5 text-blue-600"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                )}
              </button>
            ))
          )}
        </div>

        {/* Error */}
        {mutation.isError && (
          <p className="mb-4 text-sm text-red-600">
            {mutation.error instanceof Error
              ? mutation.error.message
              : "Failed to fork run"}
          </p>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleFork}
            disabled={selectedStep === null}
            loading={mutation.isPending}
          >
            Fork from Event #{(selectedStep ?? 0) + 1}
          </Button>
        </div>
      </div>
    </div>
  );
}
```

### 4.7 Resume Button Component

#### frontend/src/components/organisms/ResumeButton.tsx

```typescript
/**
 * Resume button for stopped runs.
 */

import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/atoms";
import { resumeRun } from "@/lib/api";

interface ResumeButtonProps {
  runId: string;
  canResume: boolean;
}

export function ResumeButton({ runId, canResume }: ResumeButtonProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => resumeRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["run", runId] });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  if (!canResume) {
    return null;
  }

  return (
    <Button
      variant="primary"
      size="sm"
      onClick={() => mutation.mutate()}
      loading={mutation.isPending}
    >
      Resume
    </Button>
  );
}
```

---

## 5. Acceptance Criteria

### AC-01: Fork Creates New Run
```gherkin
Given run A with 10 events
When I fork from event #5
Then a new run B is created
  And run B has events 1-5 copied
  And run B has a ForkCreated event at step 6
  And run A is unchanged
```

### AC-02: Only Forkable Events Shown
```gherkin
Given a run with various event types
When I open the fork modal
Then only PlanCreated, EvidenceCollected, ContradictionDetected, AnswerDrafted, JudgeVerdict are selectable
```

### AC-03: Resume Adds Event
```gherkin
Given a stopped run
When I click Resume
Then a ResumeStarted event is appended
  And the run status changes to RUNNING
  And previous events are preserved
```

### AC-04: Fork Preserves Lineage
```gherkin
Given run B forked from run A
When I view run B details
Then I see "Forked from Run A at step 5"
```

---

## 6. Implementation Checklist

- [ ] Create `backend/app/services/fork_service.py`
- [ ] Add fork/resume endpoints to `backend/app/routes/runs.py`
- [ ] Update `frontend/src/lib/api.ts` with fork/resume
- [ ] Create `frontend/src/components/organisms/ForkModal.tsx`
- [ ] Create `frontend/src/components/organisms/ResumeButton.tsx`
- [ ] Update ActionBar to include Fork/Resume buttons
- [ ] Write unit tests for ForkService
- [ ] Write integration tests for endpoints
- [ ] Test fork navigation

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | pytest | ForkService | 100% |
| Integration | pytest | Fork/Resume endpoints | 100% |
| Unit | Vitest + RTL | ForkModal | 100% |

## 8. Environment Variables

_None required._

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Copying many events slow | Med | Low | Batch insert |
| Fork chains get confusing | Low | Med | Show lineage in UI |

## 10. Out of Scope

- Merge forks
- Delete forks
- Fork visualizations (graph view)

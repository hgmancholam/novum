# BRD-10: SSE Streaming & Resume

**Document ID:** BRD-10
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 11 of 19

---

## 1. Executive Summary

Implement Server-Sent Events (SSE) streaming for real-time event delivery to the frontend, with heartbeat (15s), Last-Event-ID resume support, and live cancellation per RF-08.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-08 | SSE streaming + cancellation + resume | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-03, BRD-07 | BRD-11, BRD-14 |

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    sse/
      __init__.py
      stream.py           # SSE generator
      manager.py          # Connection manager
    routes/
      events.py           # Updated SSE endpoint
frontend/
  src/
    lib/
      sse.ts              # EventSource wrapper
    hooks/
      useRunStream.ts     # React hook for streaming
```

### 4.2 SSE Stream Implementation

#### backend/app/sse/stream.py

```python
"""SSE event streaming."""

import asyncio
import json
from datetime import datetime
from typing import AsyncIterator, Any
from uuid import UUID

import structlog
from sse_starlette.sse import ServerSentEvent

from app.config import settings
from app.services.event_service import EventService

logger = structlog.get_logger()


async def event_stream(
    run_id: UUID,
    event_service: EventService,
    last_event_id: str | None = None,
    heartbeat_seconds: int = 15,
) -> AsyncIterator[ServerSentEvent]:
    """Generate SSE stream for a run.
    
    Args:
        run_id: Run to stream
        event_service: Event service for fetching events
        last_event_id: Resume from this event (step_index)
        heartbeat_seconds: Heartbeat interval
        
    Yields:
        ServerSentEvent objects
    """
    after_step = 0
    if last_event_id:
        try:
            after_step = int(last_event_id)
        except ValueError:
            pass

    logger.info(
        "sse_stream_start",
        run_id=str(run_id),
        after_step=after_step,
    )

    last_heartbeat = datetime.utcnow()

    while True:
        # Fetch new events
        events = await event_service.get_events(
            run_id=run_id,
            after_step=after_step,
            limit=50,
        )

        for event in events:
            event_id = str(event.get("step_index", ""))
            yield ServerSentEvent(
                data=json.dumps(event),
                event=event.get("type", "message"),
                id=event_id,
            )
            after_step = max(after_step, event.get("step_index", 0))

        # Check if run is stopped
        last_event = events[-1] if events else None
        if last_event and last_event.get("type") == "Stopped":
            logger.info("sse_stream_complete", run_id=str(run_id))
            break

        # Heartbeat
        now = datetime.utcnow()
        if (now - last_heartbeat).total_seconds() >= heartbeat_seconds:
            yield ServerSentEvent(
                data="",
                event="heartbeat",
                id=str(after_step),
            )
            last_heartbeat = now

        # Poll interval
        await asyncio.sleep(0.5)
```

### 4.3 Connection Manager

#### backend/app/sse/manager.py

```python
"""SSE connection manager for cancellation support."""

from typing import Dict, Set
from uuid import UUID
import structlog

logger = structlog.get_logger()


class ConnectionManager:
    """Manages active SSE connections for cancellation."""

    def __init__(self) -> None:
        # run_id -> set of connection IDs
        self._connections: Dict[UUID, Set[str]] = {}
        # run_id -> cancelled flag
        self._cancelled: Dict[UUID, bool] = {}

    def connect(self, run_id: UUID, connection_id: str) -> None:
        """Register a new connection."""
        if run_id not in self._connections:
            self._connections[run_id] = set()
        self._connections[run_id].add(connection_id)
        logger.debug("sse_connect", run_id=str(run_id), conn_id=connection_id)

    def disconnect(self, run_id: UUID, connection_id: str) -> None:
        """Unregister a connection."""
        if run_id in self._connections:
            self._connections[run_id].discard(connection_id)
            if not self._connections[run_id]:
                del self._connections[run_id]
        logger.debug("sse_disconnect", run_id=str(run_id), conn_id=connection_id)

    def cancel(self, run_id: UUID) -> None:
        """Mark a run as cancelled."""
        self._cancelled[run_id] = True
        logger.info("sse_cancelled", run_id=str(run_id))

    def is_cancelled(self, run_id: UUID) -> bool:
        """Check if a run is cancelled."""
        return self._cancelled.get(run_id, False)

    def clear_cancelled(self, run_id: UUID) -> None:
        """Clear cancelled flag."""
        self._cancelled.pop(run_id, None)

    def active_connections(self, run_id: UUID) -> int:
        """Count active connections for a run."""
        return len(self._connections.get(run_id, set()))


# Singleton
connection_manager = ConnectionManager()
```

### 4.4 Updated Events Route

#### backend/app/routes/events.py (updated)

```python
"""Event streaming endpoint (SSE) - RF-08."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.dependencies import DbSession
from app.services.event_service import EventService
from app.sse.stream import event_stream
from app.sse.manager import connection_manager

router = APIRouter(prefix="/api/runs", tags=["Events"])


@router.get("/{run_id}/events")
async def stream_events(
    run_id: UUID,
    request: Request,
    db: DbSession,
    last_event_id: str | None = Query(None, alias="Last-Event-ID"),
) -> EventSourceResponse:
    """Stream events for a run via SSE (RF-08).
    
    Features:
    - Real-time event streaming
    - Heartbeat every 15 seconds
    - Resume via Last-Event-ID header
    - Automatic cleanup on disconnect
    """
    event_service = EventService(db)
    connection_id = str(uuid4())

    async def generate():
        connection_manager.connect(run_id, connection_id)
        try:
            async for event in event_stream(
                run_id=run_id,
                event_service=event_service,
                last_event_id=last_event_id or request.headers.get("Last-Event-ID"),
            ):
                if connection_manager.is_cancelled(run_id):
                    break
                yield event
        finally:
            connection_manager.disconnect(run_id, connection_id)

    return EventSourceResponse(
        generate(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

### 4.5 Frontend SSE Client

#### frontend/src/lib/sse.ts

```typescript
/**
 * SSE client wrapper with auto-reconnect and resume support.
 */

import { API_URL } from "./constants";
import { getAuthHeaders } from "./auth";

export interface SSEOptions {
  onEvent: (event: MessageEvent) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  lastEventId?: string;
}

export class SSEClient {
  private eventSource: EventSource | null = null;
  private url: string;
  private options: SSEOptions;
  private lastEventId: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  constructor(runId: string, options: SSEOptions) {
    this.url = `${API_URL}/api/runs/${runId}/events`;
    this.options = options;
    this.lastEventId = options.lastEventId ?? null;
  }

  connect(): void {
    const url = this.lastEventId
      ? `${this.url}?Last-Event-ID=${this.lastEventId}`
      : this.url;

    this.eventSource = new EventSource(url);

    this.eventSource.onopen = () => {
      this.reconnectAttempts = 0;
      this.options.onOpen?.();
    };

    this.eventSource.onmessage = (event) => {
      if (event.lastEventId) {
        this.lastEventId = event.lastEventId;
      }
      this.options.onEvent(event);
    };

    this.eventSource.onerror = (error) => {
      this.options.onError?.(error);
      this.handleError();
    };

    // Listen for specific event types
    this.eventSource.addEventListener("Stopped", (event) => {
      this.options.onEvent(event as MessageEvent);
      this.close();
    });

    this.eventSource.addEventListener("heartbeat", () => {
      // Heartbeat received, connection is alive
    });
  }

  private handleError(): void {
    if (this.eventSource?.readyState === EventSource.CLOSED) {
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        setTimeout(() => {
          this.connect();
        }, this.reconnectDelay * this.reconnectAttempts);
      }
    }
  }

  close(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  get isConnected(): boolean {
    return this.eventSource?.readyState === EventSource.OPEN;
  }
}
```

### 4.6 React Hook

#### frontend/src/hooks/useRunStream.ts

```typescript
/**
 * React hook for streaming run events.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { SSEClient } from "@/lib/sse";

interface RunEvent {
  type: string;
  [key: string]: unknown;
}

interface UseRunStreamOptions {
  runId: string;
  enabled?: boolean;
  onEvent?: (event: RunEvent) => void;
}

interface UseRunStreamResult {
  events: RunEvent[];
  isConnected: boolean;
  isComplete: boolean;
  error: Error | null;
  reconnect: () => void;
}

export function useRunStream({
  runId,
  enabled = true,
  onEvent,
}: UseRunStreamOptions): UseRunStreamResult {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const clientRef = useRef<SSEClient | null>(null);

  const connect = useCallback(() => {
    if (!enabled || !runId) return;

    clientRef.current = new SSEClient(runId, {
      onEvent: (messageEvent) => {
        try {
          const data = JSON.parse(messageEvent.data) as RunEvent;
          setEvents((prev) => [...prev, data]);
          onEvent?.(data);

          if (data.type === "Stopped") {
            setIsComplete(true);
          }
        } catch {
          // Ignore parse errors (e.g., heartbeats)
        }
      },
      onOpen: () => {
        setIsConnected(true);
        setError(null);
      },
      onError: () => {
        setIsConnected(false);
        setError(new Error("Connection lost"));
      },
    });

    clientRef.current.connect();
  }, [runId, enabled, onEvent]);

  useEffect(() => {
    connect();
    return () => {
      clientRef.current?.close();
    };
  }, [connect]);

  const reconnect = useCallback(() => {
    clientRef.current?.close();
    setEvents([]);
    setIsComplete(false);
    connect();
  }, [connect]);

  return { events, isConnected, isComplete, error, reconnect };
}
```

---

## 5. Acceptance Criteria

### AC-01: Events Stream in Real-Time
```gherkin
Given a running research run
When events are emitted by the agent
Then they appear in the SSE stream within 500ms
```

### AC-02: Heartbeat Keeps Connection Alive
```gherkin
Given an active SSE connection
When no events occur for 15 seconds
Then a heartbeat event is sent
  And the connection remains open
```

### AC-03: Resume Works with Last-Event-ID
```gherkin
Given a stream disconnected at step_index=5
When I reconnect with Last-Event-ID=5
Then events starting from step_index=6 are sent
```

### AC-04: Stopped Event Closes Stream
```gherkin
Given a running stream
When a Stopped event is emitted
Then the stream closes gracefully
```

---

## 6. Implementation Checklist

- [ ] Create `backend/app/sse/__init__.py`
- [ ] Create `backend/app/sse/stream.py`
- [ ] Create `backend/app/sse/manager.py`
- [ ] Update `backend/app/routes/events.py`
- [ ] Create `frontend/src/lib/sse.ts`
- [ ] Create `frontend/src/hooks/useRunStream.ts`
- [ ] Write integration tests for SSE
- [ ] Test reconnection behavior

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Integration | pytest | SSE endpoint | 100% |
| Unit | Vitest | SSEClient | 100% |
| Manual | Browser | Real streaming | Smoke test |

## 8. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SSE_HEARTBEAT_SECONDS` | No | 15 | Heartbeat interval |

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Connection drops | Med | Med | Auto-reconnect + resume |
| Memory leak (many connections) | Med | Low | Connection manager cleanup |

## 10. Out of Scope

- WebSocket alternative (V2)
- Compression
- Binary events

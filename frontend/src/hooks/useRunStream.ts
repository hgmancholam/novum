/**
 * useRunStream — SSE hook for a single run (RF-08).
 *
 * Wraps `createSSEConnection` from `@/lib/sse` (which already prefixes
 * `API_URL` — L-008) and exposes a declarative interface:
 *
 *   { events, isConnected, isComplete, lastEventId, error, reconnect, close }
 *
 * The hook accumulates events in arrival order, drops `heartbeat` frames,
 * treats both `Stopped` and the synthetic `cancelled` frame as terminal,
 * and tracks `lastEventId` for resume on reconnect.
 *
 * Per `eslint.config.js`, importers of `useRunStream` are restricted to
 * `pages/` (the only layer allowed to call data hooks).
 */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  addNamedListener,
  createSSEConnection,
  parseSSEEvent,
  type SSEConnection,
} from "@/lib/sse";

export interface RunStreamEvent {
  type: string;
  step_index?: number;
  [key: string]: unknown;
}

export interface UseRunStreamOptions {
  runId: string | undefined;
  enabled?: boolean;
  onEvent?: (event: RunStreamEvent) => void;
}

export interface UseRunStreamResult {
  events: RunStreamEvent[];
  isConnected: boolean;
  isComplete: boolean;
  lastEventId: string | null;
  error: Event | null;
  reconnect: () => void;
  close: () => void;
}

export function useRunStream(
  options: UseRunStreamOptions
): UseRunStreamResult {
  const { runId, enabled = true, onEvent } = options;

  const [events, setEvents] = useState<RunStreamEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [lastEventId, setLastEventId] = useState<string | null>(null);
  const [error, setError] = useState<Event | null>(null);

  const connectionRef = useRef<SSEConnection | null>(null);
  const lastEventIdRef = useRef<string | null>(null);
  const onEventRef = useRef(onEvent);
  const [reconnectTick, setReconnectTick] = useState(0);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const close = useCallback((): void => {
    if (connectionRef.current) {
      connectionRef.current.close();
      connectionRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const reconnect = useCallback((): void => {
    setIsComplete(false);
    setError(null);
    setReconnectTick((n) => n + 1);
  }, []);

  // Reset all per-run state when `runId` changes so the events list, resume
  // cursor and terminal flags do not leak across runs when the user navigates
  // between them.
  useEffect(() => {
    lastEventIdRef.current = null;
    setEvents([]);
    setLastEventId(null);
    setIsComplete(false);
    setError(null);
  }, [runId]);

  useEffect(() => {
    if (!enabled || runId === undefined || runId.length === 0) {
      return;
    }
    if (isComplete) {
      return;
    }

    const path = `/api/runs/${runId}/events`;
    const resumeFrom = lastEventIdRef.current ?? undefined;

    const handleData = (event: MessageEvent): void => {
      let parsed: RunStreamEvent;
      try {
        parsed = parseSSEEvent<RunStreamEvent>(event);
      } catch {
        // Malformed JSON (e.g. synthetic `cancelled` frame with body `{}`).
        parsed = { type: event.type || "message" } as RunStreamEvent;
      }
      if (event.lastEventId) {
        lastEventIdRef.current = event.lastEventId;
        setLastEventId(event.lastEventId);
      }
      setEvents((prev) => [...prev, parsed]);
      onEventRef.current?.(parsed);
    };

    const handleTerminal = (event: MessageEvent): void => {
      handleData(event);
      setIsComplete(true);
      if (connectionRef.current) {
        connectionRef.current.close();
        connectionRef.current = null;
      }
      setIsConnected(false);
    };

    const handleHeartbeat = (event: MessageEvent): void => {
      // Heartbeats keep the connection alive — they are NOT business events
      // (IP-10 AC-11). Still update the resume cursor so a reconnect after a
      // long quiet period does not replay the whole stream.
      if (event.lastEventId) {
        lastEventIdRef.current = event.lastEventId;
        setLastEventId(event.lastEventId);
      }
    };

    const sseOptions: Parameters<typeof createSSEConnection>[1] = {
      onOpen: () => {
        setIsConnected(true);
        setError(null);
      },
      onMessage: handleData,
      onError: (err) => {
        setError(err);
        setIsConnected(false);
      },
    };
    if (resumeFrom !== undefined) {
      sseOptions.lastEventId = resumeFrom;
    }

    const connection = createSSEConnection(path, sseOptions);
    connectionRef.current = connection;

    // The backend emits each event with a named SSE `event:` field matching
    // its `EventType` (e.g. `PlanCreated`, `ToolCalled`). `EventSource.onmessage`
    // only fires for unnamed/`message` frames, so non-terminal business events
    // would be silently dropped without explicit listeners.
    const NON_TERMINAL_EVENT_TYPES = [
      "QuestionAsked",
      "PlanCreated",
      "PlanCritiqued",
      "PlanRevised",
      "ToolCalled",
      "EvidenceAdded",
      "ClaimCovered",
      "ClaimUncoverable",
      "SourceFailed",
      "AmbiguityDetected",
      "ContradictionDetected",
      "ContradictionResolved",
      "UserContextChallenged",
      "JudgeRuled",
      "ConfidenceMismatch",
      "AgentErrored",
      "ResumedAfterError",
      "ResumedAfterCancel",
    ] as const;

    const teardowns: Array<() => void> = [
      addNamedListener(connection.source, "Stopped", handleTerminal),
      addNamedListener(connection.source, "cancelled", handleTerminal),
      addNamedListener(connection.source, "heartbeat", handleHeartbeat),
      ...NON_TERMINAL_EVENT_TYPES.map((name) =>
        addNamedListener(connection.source, name, handleData)
      ),
    ];

    return () => {
      for (const off of teardowns) {
        off();
      }
      connection.close();
      if (connectionRef.current === connection) {
        connectionRef.current = null;
      }
      setIsConnected(false);
    };
  }, [runId, enabled, isComplete, reconnectTick]);

  return {
    events,
    isConnected,
    isComplete,
    lastEventId,
    error,
    reconnect,
    close,
  };
}

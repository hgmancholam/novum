/**
 * Tests for `useRunStream` (IP-10 AC-10, AC-11, AC-12).
 *
 * jsdom does not implement `EventSource`, so we install a hand-rolled mock
 * on `globalThis` and drive it imperatively from the tests.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

import { useRunStream } from "./useRunStream";

const RUN_ID = "00000000-0000-0000-0000-000000000001";

class MockEventSource {
  static instances: MockEventSource[] = [];

  readyState: number = 0;
  url: string;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  private listeners: Map<string, Set<(ev: MessageEvent) => void>> = new Map();

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(name: string, fn: (ev: MessageEvent) => void): void {
    let set = this.listeners.get(name);
    if (!set) {
      set = new Set();
      this.listeners.set(name, set);
    }
    set.add(fn);
  }

  removeEventListener(name: string, fn: (ev: MessageEvent) => void): void {
    this.listeners.get(name)?.delete(fn);
  }

  close(): void {
    this.readyState = MockEventSource.CLOSED;
  }

  // ---- Test-only driver methods ----

  fireOpen(): void {
    this.readyState = MockEventSource.OPEN;
    this.onopen?.(new Event("open"));
  }

  fireMessage(data: unknown, lastEventId = "1"): void {
    const ev = {
      data: JSON.stringify(data),
      lastEventId,
      type: "message",
    } as unknown as MessageEvent;
    this.onmessage?.(ev);
  }

  fireNamed(name: string, data: unknown, lastEventId = "1"): void {
    const ev = {
      data: JSON.stringify(data),
      lastEventId,
      type: name,
    } as unknown as MessageEvent;
    const set = this.listeners.get(name);
    if (set) {
      for (const fn of set) fn(ev);
    }
  }

  fireError(): void {
    this.onerror?.(new Event("error"));
  }
}

function lastSource(): MockEventSource {
  const src = MockEventSource.instances.at(-1);
  if (!src) throw new Error("No EventSource instances created");
  return src;
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useRunStream", () => {
  it("creates one EventSource targeting the run endpoint via API_URL", async () => {
    renderHook(() => useRunStream({ runId: RUN_ID }));
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBe(1);
    });
    // The URL must include the API_URL host prefix (L-008 / AC-12).
    expect(lastSource().url).toContain(`/api/runs/${RUN_ID}/events`);
    expect(lastSource().url).toMatch(/^https?:\/\//);
  });

  it("accumulates message events in arrival order", async () => {
    const { result } = renderHook(() => useRunStream({ runId: RUN_ID }));
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBe(1);
    });
    act(() => {
      lastSource().fireOpen();
      lastSource().fireMessage({ type: "ToolCalled", step_index: 1 }, "1");
      lastSource().fireMessage({ type: "EvidenceAdded", step_index: 2 }, "2");
    });
    expect(result.current.events.map((e) => e.type)).toEqual([
      "ToolCalled",
      "EvidenceAdded",
    ]);
    expect(result.current.lastEventId).toBe("2");
  });

  it("sets isConnected on open and closes the source on unmount", async () => {
    const { result, unmount } = renderHook(() =>
      useRunStream({ runId: RUN_ID })
    );
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBe(1);
    });
    act(() => {
      lastSource().fireOpen();
    });
    expect(result.current.isConnected).toBe(true);
    const src = lastSource();
    unmount();
    expect(src.readyState).toBe(MockEventSource.CLOSED);
  });

  it("sets isComplete=true when a 'Stopped' event arrives", async () => {
    const { result } = renderHook(() => useRunStream({ runId: RUN_ID }));
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBe(1);
    });
    act(() => {
      lastSource().fireOpen();
      lastSource().fireNamed(
        "Stopped",
        { type: "Stopped", stop_reason: "judge_confirmed" },
        "3"
      );
    });
    expect(result.current.isComplete).toBe(true);
    expect(result.current.events.at(-1)?.type).toBe("Stopped");
    // AC-10: only the Stopped frame is terminal.
    expect(lastSource().readyState).toBe(MockEventSource.CLOSED);
  });

  it("ignores heartbeat frames in events[] (AC-11)", async () => {
    const { result } = renderHook(() => useRunStream({ runId: RUN_ID }));
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBe(1);
    });
    act(() => {
      lastSource().fireOpen();
      lastSource().fireNamed("heartbeat", "", "5");
      lastSource().fireMessage({ type: "ToolCalled", step_index: 6 }, "6");
    });
    expect(result.current.events.map((e) => e.type)).toEqual(["ToolCalled"]);
    // Heartbeats still update the resume cursor.
    expect(result.current.lastEventId).toBe("6");
  });

  it("treats the synthetic 'cancelled' frame as terminal", async () => {
    const { result } = renderHook(() => useRunStream({ runId: RUN_ID }));
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBe(1);
    });
    act(() => {
      lastSource().fireOpen();
      lastSource().fireNamed("cancelled", {}, "9");
    });
    expect(result.current.isComplete).toBe(true);
    expect(lastSource().readyState).toBe(MockEventSource.CLOSED);
  });

  it("propagates errors via the error field", async () => {
    const { result } = renderHook(() => useRunStream({ runId: RUN_ID }));
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBe(1);
    });
    act(() => {
      lastSource().fireError();
    });
    expect(result.current.error).not.toBeNull();
    expect(result.current.isConnected).toBe(false);
  });

  it("does not connect when disabled=false", () => {
    renderHook(() => useRunStream({ runId: RUN_ID, enabled: false }));
    expect(MockEventSource.instances.length).toBe(0);
  });

  it("does not connect when runId is undefined", () => {
    renderHook(() => useRunStream({ runId: undefined }));
    expect(MockEventSource.instances.length).toBe(0);
  });

  it("closes the EventSource on unmount", async () => {
    const { unmount } = renderHook(() => useRunStream({ runId: RUN_ID }));
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBe(1);
    });
    const src = lastSource();
    unmount();
    expect(src.readyState).toBe(MockEventSource.CLOSED);
  });

  it("reconnect() opens a new EventSource and clears completion state", async () => {
    const { result } = renderHook(() => useRunStream({ runId: RUN_ID }));
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBe(1);
    });
    act(() => {
      lastSource().fireOpen();
      lastSource().fireMessage({ type: "ToolCalled", step_index: 1 }, "1");
      lastSource().fireNamed(
        "Stopped",
        { type: "Stopped", stop_reason: "judge_confirmed" },
        "2"
      );
    });
    expect(result.current.isComplete).toBe(true);

    act(() => {
      result.current.reconnect();
    });
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBe(2);
    });
    expect(result.current.isComplete).toBe(false);
    // Resume URL must carry the last_event_id we saw before completion.
    expect(lastSource().url).toContain("last_event_id=2");
  });

  it("invokes the onEvent callback for each business event", async () => {
    const onEvent = vi.fn();
    renderHook(() => useRunStream({ runId: RUN_ID, onEvent }));
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBe(1);
    });
    act(() => {
      lastSource().fireOpen();
      lastSource().fireMessage({ type: "ToolCalled", step_index: 1 }, "1");
      lastSource().fireNamed("heartbeat", "", "2");
    });
    // Heartbeat does NOT invoke the consumer callback.
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent.mock.calls[0]?.[0]).toMatchObject({ type: "ToolCalled" });
  });

  it("close() terminates the underlying EventSource", async () => {
    const { result } = renderHook(() => useRunStream({ runId: RUN_ID }));
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBe(1);
    });
    const src = lastSource();
    act(() => {
      result.current.close();
    });
    expect(src.readyState).toBe(MockEventSource.CLOSED);
    expect(result.current.isConnected).toBe(false);
  });
});

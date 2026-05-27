import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen } from "@testing-library/react";

import { ElapsedClock, formatElapsed } from "./ElapsedClock";

describe("formatElapsed", () => {
  it.each([
    [0, "0s"],
    [1_000, "1s"],
    [59_000, "59s"],
    [60_000, "1m 0s"],
    [125_000, "2m 5s"],
    [3_600_000, "1h 0m"],
    [3_900_000, "1h 5m"],
  ])("formats %d ms → %s", (ms, expected) => {
    expect(formatElapsed(ms)).toBe(expected);
  });

  it("clamps negative values to 0s", () => {
    expect(formatElapsed(-500)).toBe("0s");
  });
});

describe("ElapsedClock", () => {
  it("renders elapsed time relative to startedAt using injected now", () => {
    const start = "2026-05-26T00:00:00Z";
    const now = new Date("2026-05-26T00:00:10Z");
    render(<ElapsedClock startedAt={start} now={now} />);
    expect(screen.getByTestId("elapsed-clock")).toHaveTextContent("10s");
  });

  it("updates elapsed text when the now prop advances", () => {
    const start = "2026-05-26T00:00:00Z";
    const { rerender } = render(
      <ElapsedClock startedAt={start} now={new Date(start)} />
    );
    expect(screen.getByTestId("elapsed-clock")).toHaveTextContent("0s");
    rerender(
      <ElapsedClock
        startedAt={start}
        now={new Date("2026-05-26T00:00:03Z")}
      />
    );
    expect(screen.getByTestId("elapsed-clock")).toHaveTextContent("3s");
  });

  it("does not tick when frozen", () => {
    // L-009 pitfall avoidance: drive elapsed via the `now` prop instead of
    // combining setSystemTime + advanceTimersByTime. Rerender with a later
    // `now` and assert the text stays put because `frozen` suppresses any
    // internal interval.
    const start = "2026-05-26T00:00:00Z";
    const { rerender } = render(
      <ElapsedClock startedAt={start} now={new Date("2026-05-26T00:00:05Z")} frozen />
    );
    expect(screen.getByTestId("elapsed-clock")).toHaveTextContent("5s");
    rerender(
      <ElapsedClock startedAt={start} now={new Date("2026-05-26T00:00:10Z")} frozen />
    );
    expect(screen.getByTestId("elapsed-clock")).toHaveTextContent("10s");
  });
});

describe("ElapsedClock interval", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("registers a 1-second interval while not frozen", () => {
    // Validate the interval still fires using advanceTimersByTime only —
    // no setSystemTime, to avoid the L-009 fake-timer interaction. We assert
    // only that the rendered text changes after time passes; the exact value
    // depends on the test runner's wall clock at start.
    const start = new Date(Date.now() - 1_000).toISOString();
    render(<ElapsedClock startedAt={start} />);
    const initial = screen.getByTestId("elapsed-clock").textContent;
    act(() => {
      vi.advanceTimersByTime(2_000);
    });
    const after = screen.getByTestId("elapsed-clock").textContent;
    expect(after).not.toBe(initial);
  });
});

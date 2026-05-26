/**
 * Unit tests for format utilities.
 * BRD-00 validation: Verify formatRelative() per ui-prototype.md §9.12.
 *
 * Per workflow.md F3.S3: generate_unit_tests
 */

import { describe, expect, it } from "vitest";
import { formatRelative, formatISO, truncate, formatElapsed } from "./format";

describe("formatRelative", () => {
  // Fixed reference time for deterministic tests
  const now = new Date("2026-05-26T12:00:00Z");

  it('returns "just now" for < 60 seconds', () => {
    const date = new Date("2026-05-26T11:59:30Z"); // 30 seconds ago
    expect(formatRelative(date, now)).toBe("just now");
  });

  it('returns "<n>m ago" for < 60 minutes', () => {
    const date = new Date("2026-05-26T11:45:00Z"); // 15 minutes ago
    expect(formatRelative(date, now)).toBe("15m ago");
  });

  it('returns "<n>h ago" for < 24 hours', () => {
    const date = new Date("2026-05-26T09:00:00Z"); // 3 hours ago
    expect(formatRelative(date, now)).toBe("3h ago");
  });

  it('returns "<n>d ago" for < 7 days', () => {
    const date = new Date("2026-05-24T12:00:00Z"); // 2 days ago
    expect(formatRelative(date, now)).toBe("2d ago");
  });

  it('returns "MMM D" for ≥ 7 days same year', () => {
    const date = new Date("2026-03-14T12:00:00Z"); // Same year, > 7 days
    expect(formatRelative(date, now)).toBe("Mar 14");
  });

  it('returns "MMM D, YYYY" for different year', () => {
    const date = new Date("2025-03-14T12:00:00Z"); // Previous year
    expect(formatRelative(date, now)).toBe("Mar 14, 2025");
  });

  it("accepts ISO string input", () => {
    const dateString = "2026-05-26T11:30:00Z"; // 30 minutes ago
    expect(formatRelative(dateString, now)).toBe("30m ago");
  });

  it("uses current time as default reference", () => {
    // Just verify it doesn't throw when no reference provided
    const result = formatRelative(new Date());
    expect(typeof result).toBe("string");
  });
});

describe("formatISO", () => {
  it("formats Date object to ISO 8601", () => {
    const date = new Date("2026-05-26T12:00:00.000Z");
    expect(formatISO(date)).toBe("2026-05-26T12:00:00.000Z");
  });

  it("formats ISO string to ISO 8601", () => {
    const dateString = "2026-05-26T12:00:00Z";
    const result = formatISO(dateString);
    expect(result).toMatch(/^2026-05-26T12:00:00/);
  });
});

describe("truncate", () => {
  it("returns original string if shorter than maxLength", () => {
    expect(truncate("Hello", 10)).toBe("Hello");
  });

  it("returns original string if exactly maxLength", () => {
    expect(truncate("Hello", 5)).toBe("Hello");
  });

  it("truncates with ellipsis if longer than maxLength", () => {
    expect(truncate("Hello World", 8)).toBe("Hello W…");
  });

  it("truncates to 60 chars for RunRow (per ui-prototype.md §9.8)", () => {
    const longQuestion = "A".repeat(100);
    const result = truncate(longQuestion, 60);
    expect(result.length).toBe(60);
    expect(result.endsWith("…")).toBe(true);
  });
});

describe("formatElapsed", () => {
  it('formats seconds only as "<n>s"', () => {
    expect(formatElapsed(42)).toBe("42s");
  });

  it('formats minutes and seconds as "<n>m <n>s"', () => {
    expect(formatElapsed(120)).toBe("2m 0s");
  });

  it('formats mixed minutes and seconds as "<n>m <n>s"', () => {
    expect(formatElapsed(90)).toBe("1m 30s");
  });

  it("rounds decimal seconds", () => {
    expect(formatElapsed(42.7)).toBe("43s");
    expect(formatElapsed(42.4)).toBe("42s");
  });
});

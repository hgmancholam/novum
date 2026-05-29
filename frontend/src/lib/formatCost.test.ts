import { describe, expect, it } from "vitest";

import { formatPct, formatTokens, formatUsd } from "./formatCost";

describe("formatUsd", () => {
  it("renders 4 decimals when below $1", () => {
    expect(formatUsd(0.0421)).toBe("$0.0421");
    expect(formatUsd(0)).toBe("$0.0000");
  });

  it("renders 2 decimals at or above $1", () => {
    expect(formatUsd(1.234)).toBe("$1.23");
    expect(formatUsd(123.456)).toBe("$123.46");
  });

  it("falls back to em-dash on non-finite inputs", () => {
    expect(formatUsd(Number.NaN)).toBe("—");
    expect(formatUsd(Number.POSITIVE_INFINITY)).toBe("—");
  });
});

describe("formatTokens", () => {
  it("renders exact counts below 1K", () => {
    expect(formatTokens(0)).toBe("0");
    expect(formatTokens(847)).toBe("847");
  });

  it("uses K abbreviation between 1K and 1M", () => {
    expect(formatTokens(4_300)).toBe("4.3K");
    expect(formatTokens(999_500)).toBe("999.5K");
  });

  it("uses M abbreviation at or above 1M", () => {
    expect(formatTokens(1_200_000)).toBe("1.2M");
  });

  it("falls back to em-dash on non-finite inputs", () => {
    expect(formatTokens(Number.NaN)).toBe("—");
  });
});

describe("formatPct", () => {
  it("renders one decimal", () => {
    expect(formatPct(12.4)).toBe("12.4%");
    expect(formatPct(100)).toBe("100.0%");
    expect(formatPct(0)).toBe("0.0%");
  });

  it("falls back to em-dash on non-finite inputs", () => {
    expect(formatPct(Number.NaN)).toBe("—");
  });
});

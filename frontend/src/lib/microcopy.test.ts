import { describe, expect, it } from "vitest";

import {
  FEED_DONE,
  FEED_FETCHED_PAGE,
  FEED_LET_ME_FETCH,
  FEED_LET_ME_SEARCH,
  FEED_LET_ME_THINK,
  FEED_RESULTS_COUNT,
  FEED_SEARCHED_WEB,
  FEED_TOGGLE_COLLAPSE,
  FEED_TOGGLE_EXPAND,
  ANSWER_ANIMATE_TOGGLE,
  ANSWER_SKIP_HINT,
  TRACE_PANEL_COLLAPSE,
  TRACE_PANEL_EXPAND,
} from "./microcopy";

describe("microcopy — IP-24 (Phase 0)", () => {
  it("has feed microcopy constants present", () => {
    expect(FEED_LET_ME_SEARCH).toContain("{query}");
    expect(FEED_LET_ME_FETCH).toBeTruthy();
    expect(FEED_LET_ME_THINK).toBeTruthy();
    expect(FEED_SEARCHED_WEB).toBeTruthy();
    expect(FEED_FETCHED_PAGE).toBeTruthy();
    expect(FEED_DONE).toBe("Listo");
    expect(FEED_TOGGLE_COLLAPSE).toBeTruthy();
    expect(FEED_TOGGLE_EXPAND).toBeTruthy();
    expect(TRACE_PANEL_COLLAPSE).toBeTruthy();
    expect(TRACE_PANEL_EXPAND).toBeTruthy();
    expect(ANSWER_SKIP_HINT).toBeTruthy();
    expect(ANSWER_ANIMATE_TOGGLE).toBeTruthy();
  });

  it("FEED_RESULTS_COUNT pluralizes correctly", () => {
    expect(FEED_RESULTS_COUNT(0)).toBe("0 resultados");
    expect(FEED_RESULTS_COUNT(1)).toBe("1 resultado");
    expect(FEED_RESULTS_COUNT(5)).toBe("5 resultados");
  });
});

import { describe, it, expect, beforeEach } from "vitest";
import {
  hasAnswerBeenAnimated,
  markAnswerAnimated,
  isAnimateAnswerEnabled,
  setAnimateAnswerEnabled,
} from "./answerAnimation";

describe("answerAnimation — IP-24 Phase 3.5", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe("hasAnswerBeenAnimated / markAnswerAnimated", () => {
    it("returns false for never-animated run", () => {
      expect(hasAnswerBeenAnimated("run-123")).toBe(false);
    });

    it("returns true after marking as animated", () => {
      markAnswerAnimated("run-123");
      expect(hasAnswerBeenAnimated("run-123")).toBe(true);
    });

    it("persists multiple runs", () => {
      markAnswerAnimated("run-1");
      markAnswerAnimated("run-2");
      expect(hasAnswerBeenAnimated("run-1")).toBe(true);
      expect(hasAnswerBeenAnimated("run-2")).toBe(true);
    });

    it("does not duplicate entries", () => {
      markAnswerAnimated("run-123");
      markAnswerAnimated("run-123");
      const stored = localStorage.getItem("novum_answered_runs");
      const runs: unknown = stored ? JSON.parse(stored) : [];
      expect(runs).toEqual(["run-123"]);
    });

    it("caps at 500 entries, dropping oldest", () => {
      for (let i = 0; i < 550; i++) {
        markAnswerAnimated(`run-${i}`);
      }
      const stored = localStorage.getItem("novum_answered_runs");
      const runs: unknown = stored ? JSON.parse(stored) : [];
      expect(Array.isArray(runs) && runs.length).toBe(500);
      // Oldest (run-0 through run-49) should be dropped
      expect(hasAnswerBeenAnimated("run-0")).toBe(false);
      expect(hasAnswerBeenAnimated("run-50")).toBe(true);
      expect(hasAnswerBeenAnimated("run-549")).toBe(true);
    });

    it("recovers from corrupted localStorage", () => {
      localStorage.setItem("novum_answered_runs", "not valid json");
      expect(hasAnswerBeenAnimated("run-123")).toBe(false);
      markAnswerAnimated("run-123");
      expect(hasAnswerBeenAnimated("run-123")).toBe(true);
    });
  });

  describe("isAnimateAnswerEnabled / setAnimateAnswerEnabled", () => {
    it("defaults to true when key is missing", () => {
      expect(isAnimateAnswerEnabled()).toBe(true);
    });

    it("returns false after setting to false", () => {
      setAnimateAnswerEnabled(false);
      expect(isAnimateAnswerEnabled()).toBe(false);
    });

    it("returns true after setting to true", () => {
      setAnimateAnswerEnabled(true);
      expect(isAnimateAnswerEnabled()).toBe(true);
    });

    it("round-trips correctly", () => {
      setAnimateAnswerEnabled(false);
      expect(isAnimateAnswerEnabled()).toBe(false);
      setAnimateAnswerEnabled(true);
      expect(isAnimateAnswerEnabled()).toBe(true);
    });
  });
});

/**
 * Answer animation persistence helpers — IP-24 Phase 3.5.
 *
 * Tracks which runs have already had their answer animated (localStorage).
 * Prevents re-animation on replay. Global toggle for animation preference.
 */

const ANSWERED_RUNS_KEY = "novum_answered_runs";
const ANIMATE_ANSWER_KEY = "novum_animate_answer";
const MAX_ANSWERED_RUNS = 500;

/**
 * Check if a run has already been animated.
 */
export function hasAnswerBeenAnimated(runId: string): boolean {
  try {
    const stored = localStorage.getItem(ANSWERED_RUNS_KEY);
    if (!stored) return false;
    const runs: unknown = JSON.parse(stored);
    if (!Array.isArray(runs)) return false;
    return runs.includes(runId);
  } catch {
    return false;
  }
}

/**
 * Mark a run as animated (persists to localStorage).
 */
export function markAnswerAnimated(runId: string): void {
  try {
    const stored = localStorage.getItem(ANSWERED_RUNS_KEY);
    let runs: string[] = [];
    if (stored) {
      try {
        const parsed: unknown = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          runs = parsed.filter((id): id is string => typeof id === "string");
        }
      } catch {
        // Ignore parse errors, start fresh
      }
    }

    if (!runs.includes(runId)) {
      runs.push(runId);
    }

    // Cap at MAX_ANSWERED_RUNS, drop oldest
    if (runs.length > MAX_ANSWERED_RUNS) {
      runs = runs.slice(runs.length - MAX_ANSWERED_RUNS);
    }

    localStorage.setItem(ANSWERED_RUNS_KEY, JSON.stringify(runs));
  } catch {
    // Ignore storage errors
  }
}

/**
 * Global toggle: is answer animation enabled?
 */
export function isAnimateAnswerEnabled(): boolean {
  try {
    const stored = localStorage.getItem(ANIMATE_ANSWER_KEY);
    if (stored === null) return true; // Default enabled
    return stored === "1";
  } catch {
    return true;
  }
}

/**
 * Set the global animation preference.
 */
export function setAnimateAnswerEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(ANIMATE_ANSWER_KEY, enabled ? "1" : "0");
  } catch {
    // Ignore storage errors
  }
}

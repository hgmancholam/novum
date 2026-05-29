/**
 * History-related types — BRD-12.
 *
 * `RunSummary` is the client-side projection of the backend `RunListItem`
 * with a derived `status` field. See `mapRun` in `hooks/useRunHistory`.
 */

import type { StopReason } from "./events";

export type RunStatus = "running" | "completed" | "stopped";

export interface RunSummary {
  id: string;
  username: string;
  question: string;
  status: RunStatus;
  stopReason: StopReason | null;
  startedAt: string;
  stoppedAt: string | null;
  llmProvider: string;
}

/**
 * Filter value for the stop-reason chip row.
 *
 * `"honest_any"` is a UI-only sentinel that groups the three honest-stop
 * reasons (`honest_unanswerable`, `honest_contradiction`, `honest_ambiguous`)
 * under a single chip — they share the same user-facing meaning
 * ("the agent admitted it could not give a confident answer") and individually
 * are too rare to deserve their own button.
 */
export type StopReasonFilter = StopReason | "honest_any";

export const HONEST_STOP_REASONS: ReadonlyArray<StopReason> = [
  "honest_unanswerable",
  "honest_contradiction",
  "honest_ambiguous",
];

export interface HistoryFilterValues {
  status?: RunStatus;
  stopReason?: StopReasonFilter;
  search?: string;
}

/**
 * Cursor-paginated history page (BRD-20 §4.4).
 *
 * Wire shape from `GET /api/runs` is snake_case
 * (`{ items, has_more, next_cursor }`); we expose the camelCase
 * projection consistent with the rest of the FE types layer.
 */
export interface RunHistoryPage {
  items: RunSummary[];
  hasMore: boolean;
  nextCursor: string | null;
}

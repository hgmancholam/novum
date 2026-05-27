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
}

export interface HistoryFilterValues {
  status?: RunStatus;
  stopReason?: StopReason;
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

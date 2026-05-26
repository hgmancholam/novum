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

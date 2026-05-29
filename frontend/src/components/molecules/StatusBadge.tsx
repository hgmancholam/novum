/**
 * StatusBadge molecule — renders run status / stop_reason as a labeled Badge.
 * Microcopy and color mapping per ui-prototype.md §7.4 and §3.2 (RF-02).
 */

import { Badge, type BadgeVariant } from "@/components/atoms";
import { ANSWER_KIND_BEST_EFFORT_LABEL } from "@/lib/microcopy";
import type { AnswerKind, StopReason } from "@/types/events";

export type RunStatus = "running" | "completed" | "stopped";

export interface StatusBadgeProps {
  status: RunStatus;
  stopReason?: StopReason;
  /** Optional failure reason shown after "Errored —" when stopReason === "errored". */
  errorReason?: string;
  /** RF-17: when stopReason is `stopped_by_budget` and answerKind is `best_effort`,
   * the badge surfaces the best-effort outcome instead of the generic budget stop. */
  answerKind?: AnswerKind | null;
  className?: string;
}

const stopReasonLabels: Record<StopReason, string> = {
  judge_confirmed: "Judge confirmed",
  stopped_by_budget: "Stopped on budget",
  user_cancelled: "Cancelled",
  errored: "Errored",
};

const stopReasonVariants: Record<StopReason, BadgeVariant> = {
  judge_confirmed: "success",
  stopped_by_budget: "warning",
  user_cancelled: "secondary",
  errored: "error",
};

export function StatusBadge({
  status,
  stopReason,
  errorReason,
  answerKind,
  className,
}: StatusBadgeProps) {
  if (status === "running") {
    return (
      <Badge variant="info" className={className}>
        Researching…
      </Badge>
    );
  }

  if (stopReason !== undefined) {
    const isBestEffort =
      stopReason === "stopped_by_budget" && answerKind === "best_effort";
    const baseLabel = isBestEffort
      ? ANSWER_KIND_BEST_EFFORT_LABEL
      : stopReasonLabels[stopReason];
    const label =
      stopReason === "errored" && errorReason !== undefined && errorReason !== ""
        ? `${baseLabel} — ${errorReason}`
        : baseLabel;
    return (
      <Badge variant={stopReasonVariants[stopReason]} className={className}>
        {label}
      </Badge>
    );
  }

  return (
    <Badge variant="default" className={className}>
      Unknown
    </Badge>
  );
}

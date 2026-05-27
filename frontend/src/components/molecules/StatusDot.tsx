/**
 * StatusDot molecule — compact color-only indicator for run status / stop_reason.
 * Same semantic mapping as StatusBadge (ui-prototype.md §7.4, RF-02) but
 * renders as a small colored dot with an accessible label (aria-label + title)
 * for the history list (BRD-12 §4.7).
 */

import { cn } from "@/lib/cn";
import type { StopReason } from "@/types/events";
import type { RunStatus } from "./StatusBadge";

export interface StatusDotProps {
  status: RunStatus;
  stopReason?: StopReason;
  className?: string;
}

const stopReasonLabels: Record<StopReason, string> = {
  judge_confirmed: "Judge confirmed",
  stopped_by_budget: "Stopped on budget",
  user_cancelled: "Cancelled",
  errored: "Errored",
};

type Tone = "success" | "warning" | "danger" | "neutral" | "info";

const stopReasonTones: Record<StopReason, Tone> = {
  judge_confirmed: "success",
  stopped_by_budget: "warning",
  user_cancelled: "neutral",
  errored: "danger",
};

const toneStyles: Record<Tone, string> = {
  success: "bg-(--semantic-success) shadow-[0_0_8px_var(--semantic-success)]",
  warning: "bg-(--semantic-warning) shadow-[0_0_8px_var(--semantic-warning)]",
  danger: "bg-(--semantic-danger) shadow-[0_0_8px_var(--semantic-danger)]",
  neutral: "bg-(--semantic-neutral)",
  info: "bg-(--accent) shadow-[0_0_8px_var(--accent)]",
};

export function StatusDot({ status, stopReason, className }: StatusDotProps) {
  let tone: Tone;
  let label: string;
  let pulse = false;

  if (status === "running") {
    tone = "info";
    label = "Researching…";
    pulse = true;
  } else if (stopReason !== undefined) {
    tone = stopReasonTones[stopReason];
    label = stopReasonLabels[stopReason];
  } else {
    tone = "neutral";
    label = "Unknown";
  }

  return (
    <span
      role="status"
      aria-label={label}
      title={label}
      data-testid="status-dot"
      data-tone={tone}
      className={cn(
        "inline-block h-2 w-2 shrink-0 rounded-full",
        toneStyles[tone],
        pulse && "animate-pulse",
        className
      )}
    />
  );
}

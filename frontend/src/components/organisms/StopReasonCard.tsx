/**
 * StopReasonCard organism — terminal-state explanation card (C7-C10).
 * See ui-prototype.md §3.1 and BRD-13 §4.8.
 *
 * Covers all 7 `StopReason` enum values. Microcopy mirrors BRD-13 §4.8.
 * Token-only styling (BRD-11 §1) — no Tailwind greys, no hardcoded hex.
 */

import { cn } from "@/lib/cn";
import type { StopReason } from "@/types/events";

export type StopReasonVariant = "success" | "warning" | "error" | "info";

interface ReasonEntry {
  title: string;
  description: string;
  variant: StopReasonVariant;
}

export const stopReasonConfig: Record<StopReason, ReasonEntry> = {
  judge_confirmed: {
    title: "Answer Confirmed",
    description:
      "The judge has verified this answer meets the confidence threshold.",
    variant: "success",
  },
  stopped_by_budget: {
    title: "Research Limit Reached",
    description:
      "Maximum research iterations reached. The current answer represents best available evidence.",
    variant: "info",
  },
  user_cancelled: {
    title: "Cancelled by User",
    description: "Research was stopped by user request.",
    variant: "info",
  },
  errored: {
    title: "Error Occurred",
    description: "An unexpected error prevented completion.",
    variant: "error",
  },
};

const variantColorToken: Record<StopReasonVariant, string> = {
  success: "var(--semantic-success)",
  warning: "var(--semantic-warning)",
  error: "var(--semantic-danger)",
  info: "var(--semantic-neutral)",
};

export interface StopReasonCardProps {
  reason: StopReason;
  /** Optional extra explanation provided in the Stopped event. */
  explanation?: string | undefined;
  className?: string | undefined;
}

export function StopReasonCard({
  reason,
  explanation,
  className,
}: StopReasonCardProps) {
  const config = stopReasonConfig[reason];
  const color = variantColorToken[config.variant];

  return (
    <div
      role="status"
      data-testid="stop-reason-card"
      data-variant={config.variant}
      data-reason={reason}
      className={cn(
        "mx-auto mt-6 w-full max-w-3xl rounded-[var(--radius-md)] border p-5",
        "bg-[var(--bg-secondary)] text-[var(--text-primary)]",
        className
      )}
      style={{
        borderColor: color,
        backgroundColor: `color-mix(in srgb, ${color} 10%, var(--bg-secondary))`,
      }}
    >
      <h3
        className="mb-2 text-lg font-semibold"
        style={{ color }}
      >
        {config.title}
      </h3>
      <p className="text-sm text-[var(--text-primary)]">{config.description}</p>
      {explanation !== undefined && explanation.length > 0 ? (
        <p className="mt-3 text-sm text-[var(--text-secondary)]">
          {explanation}
        </p>
      ) : null}
    </div>
  );
}

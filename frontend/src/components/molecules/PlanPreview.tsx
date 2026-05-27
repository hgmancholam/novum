/**
 * PlanPreview molecule — T1b narrative shown when a run has just started
 * but no `PlanCreated` has arrived yet. Microcopy is verbatim from
 * ui-prototype.md §7.
 */

import { Compass } from "lucide-react";

import { cn } from "@/lib/cn";

export interface PlanPreviewProps {
  className?: string | undefined;
}

export const PLAN_PREVIEW_STEPS: readonly string[] = [
  "Classify the question type",
  "Plan sub-claims to cover",
  "Search the web and Wikipedia",
  "Check source agreement and contradictions",
  "Have a judge verify sufficiency",
  "Answer — or honest-stop if it cannot.",
];

export function PlanPreview({ className }: PlanPreviewProps) {
  return (
    <section
      data-testid="plan-preview"
      aria-label="Plan preview"
      className={cn(
        "glass-subtle rounded-[var(--radius-md)] p-3",
        className
      )}
    >
      <header className="flex items-center gap-2 text-[var(--text-primary)]">
        <Compass
          aria-hidden="true"
          width={14}
          height={14}
          style={{ color: "var(--accent)" }}
        />
        <span className="text-xs font-medium">Novum will:</span>
      </header>
      <ol className="mt-2 ml-5 list-decimal space-y-1 text-xs text-[var(--text-secondary)]">
        {PLAN_PREVIEW_STEPS.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      <p className="mt-2 text-[10px] text-[var(--text-muted)]">
        Events will appear below as they happen.
      </p>
    </section>
  );
}

/**
 * TrustSummary organism — surface RF §6-quater guarantees on terminal states.
 *
 * Without an event stream (SSE deferred to BRD-10), this iter 2 renders a
 * "deterministic from RunResponse" view: who/when/format/threshold + the
 * 7-enum stop_reason microcopy. Confidence/iteration/source metrics show
 * `—` placeholders that BRD-10/14 will fill in. The point is to never hide
 * a trust dimension (RF-13).
 *
 * Microcopy per ui-prototype.md §7.7 / §7.4. Token-only styling.
 */

import { cn } from "@/lib/cn";
import { formatRelative } from "@/lib/format";
import type { Run } from "@/types/run";
import type { StopReason } from "@/types/events";
import { stopReasonConfig } from "./StopReasonCard";

export interface TrustSummaryProps {
  run: Run;
  className?: string | undefined;
}

/**
 * Build the §7.7 line-1 summary string for the current run.
 * `—` is rendered for confidence values that the event log (BRD-10) will fill.
 */
function buildSummaryLine(run: Run): string {
  const reason: StopReason | null = run.stopReason;
  const threshold = run.confidenceThreshold.toFixed(2);
  if (reason === null) {
    return `\u00b7 Researching \u00b7 threshold ${threshold}`;
  }
  switch (reason) {
    case "judge_confirmed":
      return `\u2713 Judge confirmed \u00b7 confidence \u2014 / threshold ${threshold}`;
    case "honest_unanswerable":
      return "\u26a0 Honest stop \u00b7 question is unanswerable";
    case "honest_contradiction":
      return "\u26a0 Honest stop \u00b7 sources disagree";
    case "honest_ambiguous":
      return "\u26a0 Honest stop \u00b7 question is ambiguous";
    case "stopped_by_budget":
      return "\u26a0 Stopped on budget \u00b7 best-effort answer";
    case "user_cancelled":
      return "\u2298 Cancelled \u00b7 partial trace preserved";
    case "errored":
      return "\u26a0 Errored \u00b7 see details";
  }
}

function Row({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="grid grid-cols-[140px_1fr] items-baseline gap-3 py-1">
      <dt
        className="text-xs uppercase tracking-wide text-[var(--text-muted)]"
        title={hint}
      >
        {label}
      </dt>
      <dd className="text-sm text-[var(--text-primary)]">{children}</dd>
    </div>
  );
}

const PENDING = (
  <span
    className="text-[var(--text-muted)]"
    title="Available once the event log is wired (BRD-10)"
  >
    —
  </span>
);

export function TrustSummary({ run, className }: TrustSummaryProps) {
  const reasonTitle =
    run.stopReason !== null ? stopReasonConfig[run.stopReason].title : "Running";
  const summaryLine = buildSummaryLine(run);

  return (
    <section
      data-testid="trust-summary"
      aria-labelledby="trust-summary-title"
      className={cn(
        "mx-auto w-full max-w-3xl rounded-[var(--radius-md)] border",
        "border-[var(--glass-border)] bg-[var(--bg-secondary)] p-5",
        className
      )}
    >
      <h3
        id="trust-summary-title"
        className="mb-3 text-sm font-medium text-[var(--text-primary)]"
      >
        Trust summary
      </h3>
      <p
        data-testid="trust-summary-line"
        className="mb-3 text-sm text-[var(--text-primary)]"
      >
        {summaryLine}
      </p>
      <dl>
        <Row label="Outcome" hint="One of 7 enum stop_reason values (RF-02)">
          {reasonTitle}
        </Row>
        <Row label="Threshold" hint="User-selected confidence threshold (RF-12)">
          {run.confidenceThreshold.toFixed(2)}
        </Row>
        <Row
          label="Confidence"
          hint="final_confidence = min(structural, judge) — pending event log (RF-12)"
        >
          <div className="flex items-center gap-2">
            <div
              aria-hidden="true"
              className="h-2 w-40 rounded-full bg-[var(--bg-tertiary)]"
            />
            {PENDING}
          </div>
        </Row>
        <Row label="Iterations" hint="Pending event log (RF-03)">
          {PENDING}
        </Row>
        <Row label="Sources" hint="Pending event log (RF-04)">
          {PENDING}
        </Row>
        <Row label="Started">{formatRelative(run.startedAt)}</Row>
        {run.stoppedAt !== null ? (
          <Row label="Stopped">{formatRelative(run.stoppedAt)}</Row>
        ) : null}
      </dl>
      <p className="mt-3 text-xs text-[var(--text-muted)]">
        Per-step evidence and confidence will appear here once the trace
        stream is enabled.
      </p>
    </section>
  );
}

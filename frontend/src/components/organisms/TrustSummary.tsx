/**
 * TrustSummary organism — surface RF §6-quater guarantees on terminal states.
 *
 * Renders trust metrics from the event log when available (JudgeRuled event),
 * falling back to `—` placeholders for metrics not yet received.
 *
 * Microcopy per ui-prototype.md §7.7 / §7.4. Token-only styling.
 */

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { formatRelative, formatElapsed } from "@/lib/format";
import type { Run } from "@/types/run";
import type { StopReason } from "@/types/events";
import { stopReasonConfig } from "./StopReasonCard";

export interface JudgeConfidenceMetrics {
  finalConfidence: number;
  structuralConfidence: number;
  judgeConfidence: number;
  passed: boolean;
}

/**
 * Best-effort structural fallback surfaced when the judge never confirmed
 * (e.g. DEEP lane hit the ReAct budget). Mirrors `stop_rationale.confidence`
 * with `confidence_kind = "structural"` (backend PR-1 Mejora 2.2).
 */
export interface StructuralConfidenceFallback {
  confidence: number;
  kind: "structural";
}

export interface TrustSummaryProps {
  run: Run;
  /** Confidence metrics from the JudgeRuled event (RF-12). */
  judgeConfidence?: JudgeConfidenceMetrics | null | undefined;
  /** Structural fallback from `stop_rationale` when judge did not confirm. */
  structuralFallback?: StructuralConfidenceFallback | null | undefined;
  /** Total unique sources collected (from EvidenceAdded events). */
  sourceCount?: number | null | undefined;
  className?: string | undefined;
}

/**
 * Build the §7.7 line-1 summary string for the current run.
 */
function buildSummaryLine(
  run: Run,
  judgeConfidence?: JudgeConfidenceMetrics | null,
  structuralFallback?: StructuralConfidenceFallback | null
): string {
  const reason: StopReason | null = run.stopReason;
  const threshold = run.confidenceThreshold.toFixed(2);
  if (reason === null) {
    return `· Researching · threshold ${threshold}`;
  }
  switch (reason) {
    case "judge_confirmed": {
      const confStr =
        judgeConfidence !== null && judgeConfidence !== undefined
          ? `${Math.round(judgeConfidence.finalConfidence * 100)}%`
          : "—";
      return `✓ Judge confirmed · confidence ${confStr} / threshold ${threshold}`;
    }
    case "stopped_by_budget": {
      if (structuralFallback !== null && structuralFallback !== undefined) {
        const pct = Math.round(structuralFallback.confidence * 100);
        return `⚠ Stopped on budget · structural confidence ${pct}% · judge not confirmed`;
      }
      return "⚠ Stopped on budget · best-effort answer";
    }
    case "user_cancelled":
      return "⊘ Cancelled · partial trace preserved";
    case "errored":
      return "⚠ Errored · see details";
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
        className="text-xs uppercase tracking-wide text-(--text-muted)"
        title={hint}
      >
        {label}
      </dt>
      <dd className="text-sm text-(--text-primary)">{children}</dd>
    </div>
  );
}

const PENDING = (
  <span
    className="text-(--text-muted)"
    title="Available once the event log is wired (BRD-10)"
  >
    —
  </span>
);

function ConfidenceRow({ metrics }: { metrics: JudgeConfidenceMetrics }) {
  const pct = Math.round(metrics.finalConfidence * 100);
  const color = metrics.passed
    ? "bg-[var(--semantic-success)]"
    : "bg-[var(--semantic-warning)]";
  const textColor = metrics.passed
    ? "text-[var(--semantic-success)]"
    : "text-[var(--semantic-warning)]";

  return (
    <div className="flex items-center gap-3">
      <div
        role="progressbar"
        aria-label={`Confidence ${pct}%`}
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        className="relative h-2 w-32 overflow-hidden rounded-full bg-(--bg-tertiary)"
      >
        <div
          className={cn("absolute inset-y-0 left-0 rounded-full transition-all", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={cn("text-sm font-semibold tabular-nums", textColor)}>
        {pct}%
      </span>
      <span className="text-xs text-(--text-muted)">
        structural {Math.round(metrics.structuralConfidence * 100)}% · judge{" "}
        {Math.round(metrics.judgeConfidence * 100)}%
      </span>
    </div>
  );
}

interface ElapsedValueProps {
  startedAt: string | Date;
  stoppedAt: string | Date | null;
}

function StructuralFallbackRow({
  fallback,
}: {
  fallback: StructuralConfidenceFallback;
}) {
  const pct = Math.round(fallback.confidence * 100);
  return (
    <div className="flex items-center gap-3">
      <div
        role="progressbar"
        aria-label={`Structural confidence ${pct}%`}
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        className="relative h-2 w-32 overflow-hidden rounded-full bg-(--bg-tertiary)"
      >
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-(--semantic-warning) transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm font-semibold tabular-nums text-(--semantic-warning)">
        {pct}%
      </span>
      <span className="text-xs text-(--text-muted)">
        structural · judge not confirmed
      </span>
    </div>
  );
}

function toMs(value: string | Date): number {
  return value instanceof Date ? value.getTime() : new Date(value).getTime();
}

function ElapsedValue({ startedAt, stoppedAt }: ElapsedValueProps) {
  const isRunning = stoppedAt === null;
  const [now, setNow] = useState<number>(() => Date.now());

  useEffect(() => {
    if (!isRunning) return;
    const tick = window.setInterval(() => { setNow(Date.now()); }, 1000);
    return () => { window.clearInterval(tick); };
  }, [isRunning]);

  const startMs = toMs(startedAt);
  const endMs = stoppedAt !== null ? toMs(stoppedAt) : now;
  const seconds = Math.max(0, (endMs - startMs) / 1000);
  return <span className="tabular-nums">{formatElapsed(seconds)}</span>;
}

export function TrustSummary({
  run,
  judgeConfidence,
  structuralFallback,
  sourceCount,
  className,
}: TrustSummaryProps) {
  const reasonTitle =
    run.stopReason !== null ? stopReasonConfig[run.stopReason].title : "Running";
  const summaryLine = buildSummaryLine(run, judgeConfidence, structuralFallback);
  const hasLiveMetrics =
    judgeConfidence !== null && judgeConfidence !== undefined;
  const hasStructuralFallback =
    !hasLiveMetrics &&
    structuralFallback !== null &&
    structuralFallback !== undefined;

  return (
    <section
      data-testid="trust-summary"
      aria-labelledby="trust-summary-title"
      className={cn(
        "mx-auto w-full max-w-3xl rounded-md border",
        "border-(--glass-border) bg-(--bg-secondary) p-5",
        className
      )}
    >
      <h3
        id="trust-summary-title"
        className="mb-3 text-sm font-medium text-(--text-primary)"
      >
        Trust summary
      </h3>
      <p
        data-testid="trust-summary-line"
        className="mb-3 text-sm text-(--text-primary)"
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
          hint="final_confidence = min(structural, judge) — RF-12"
        >
          {hasLiveMetrics ? (
            <ConfidenceRow metrics={judgeConfidence} />
          ) : hasStructuralFallback ? (
            <StructuralFallbackRow fallback={structuralFallback} />
          ) : (
            <div className="flex items-center gap-2">
              <div
                aria-hidden="true"
                className="h-2 w-32 rounded-full bg-(--bg-tertiary)"
              />
              {PENDING}
            </div>
          )}
        </Row>
        <Row label="Sources" hint="Unique sources collected (RF-04)">
          {sourceCount !== null && sourceCount !== undefined ? (
            <span>{sourceCount} source{sourceCount !== 1 ? "s" : ""}</span>
          ) : (
            PENDING
          )}
        </Row>
        <Row label="Started">{formatRelative(run.startedAt)}</Row>
        <Row label="Elapsed" hint="Tiempo total entre el inicio y el cierre del run">
          <ElapsedValue
            startedAt={run.startedAt}
            stoppedAt={run.stoppedAt}
          />
        </Row>
      </dl>
      {!hasLiveMetrics && (
        <p className="mt-3 text-xs text-(--text-muted)">
          Per-step evidence and confidence will appear here once the trace
          stream is enabled.
        </p>
      )}
    </section>
  );
}

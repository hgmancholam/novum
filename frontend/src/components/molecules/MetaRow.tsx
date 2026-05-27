/**
 * MetaRow molecule — inline metadata chips for a run.
 * Surfaced in `RunHeader` and `TrustSummary`.
 *
 * Renders: started-at relative · duration (when terminal) · format · threshold.
 */

import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/cn";
import { formatElapsed } from "./ElapsedClock";

export interface MetaRowProps {
  startedAt: string;
  stoppedAt: string | null;
  outputFormat: "prose" | "structured";
  confidenceThreshold: number;
  ownerUsername: string;
  className?: string | undefined;
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-[var(--radius-sm)] border border-[var(--glass-border)] bg-[var(--glass-bg)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
      {children}
    </span>
  );
}

export function MetaRow({
  startedAt,
  stoppedAt,
  outputFormat,
  confidenceThreshold,
  ownerUsername,
  className,
}: MetaRowProps) {
  const duration =
    stoppedAt !== null
      ? formatElapsed(
          new Date(stoppedAt).getTime() - new Date(startedAt).getTime()
        )
      : null;
  const formatLabel = outputFormat === "structured" ? "Structured" : "Prose";

  return (
    <div
      data-testid="meta-row"
      className={cn("flex flex-wrap items-center gap-2", className)}
    >
      <Chip>
        <span className="text-[var(--text-muted)]">@</span>
        {ownerUsername}
      </Chip>
      <Chip>
        <span aria-hidden="true">·</span>
        <span title={new Date(startedAt).toISOString()}>
          started {formatRelative(startedAt)}
        </span>
      </Chip>
      {duration !== null ? (
        <Chip>
          <span aria-hidden="true">·</span>
          <span>duration {duration}</span>
        </Chip>
      ) : null}
      <Chip>
        <span aria-hidden="true">·</span>
        <span>format {formatLabel}</span>
      </Chip>
      <Chip>
        <span aria-hidden="true">·</span>
        <span title="Confidence threshold (RF-12)">
          threshold {confidenceThreshold.toFixed(2)}
        </span>
      </Chip>
    </div>
  );
}

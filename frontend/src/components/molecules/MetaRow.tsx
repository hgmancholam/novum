/**
 * MetaRow molecule — inline metadata chips for a run.
 * Surfaced in `RunHeader` and `TrustSummary`.
 *
 * Renders: started-at relative · duration (when terminal) · format · threshold.
 */

import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/cn";
import { PROVIDER_LABELS, type LlmProviderName } from "@/lib/providers";
import { formatElapsed } from "./ElapsedClock";

export interface MetaRowProps {
  startedAt: string;
  stoppedAt: string | null;
  outputFormat: "prose" | "structured";
  confidenceThreshold: number;
  ownerUsername: string;
  llmProvider?: string;
  className?: string | undefined;
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="glass-subtle inline-flex items-center gap-1 rounded-[var(--radius-sm)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
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
  llmProvider,
  className,
}: MetaRowProps) {
  const duration =
    stoppedAt !== null
      ? formatElapsed(
          new Date(stoppedAt).getTime() - new Date(startedAt).getTime()
        )
      : null;
  const formatLabel = outputFormat === "structured" ? "Structured" : "Prose";
  const providerLabel =
    llmProvider !== undefined && llmProvider in PROVIDER_LABELS
      ? PROVIDER_LABELS[llmProvider as LlmProviderName]
      : llmProvider;

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
      {providerLabel !== undefined ? (
        <Chip>
          <span aria-hidden="true">·</span>
          <span title="LLM provider used for this run">{providerLabel}</span>
        </Chip>
      ) : null}
    </div>
  );
}

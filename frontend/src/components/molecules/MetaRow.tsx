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

function Chip({
  children,
  title,
}: {
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className="glass-subtle inline-flex items-center gap-1 rounded-[var(--radius-sm)] px-1.5 py-0.5 text-xs text-[var(--text-secondary)] whitespace-nowrap"
    >
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
      className={cn("flex flex-wrap items-center gap-1.5", className)}
    >
      <Chip>
        <span className="text-[var(--text-muted)]">@</span>
        {ownerUsername}
      </Chip>
      <Chip title={new Date(startedAt).toISOString()}>
        <span>started {formatRelative(startedAt)}</span>
      </Chip>
      {duration !== null ? (
        <Chip title="Total elapsed time">
          <span>{duration}</span>
        </Chip>
      ) : null}
      <Chip title={`Output format: ${formatLabel}`}>
        <span>{formatLabel}</span>
      </Chip>
      <Chip title="Confidence threshold (RF-12)">
        <span>threshold {confidenceThreshold.toFixed(2)}</span>
      </Chip>
      {providerLabel !== undefined ? (
        <Chip title="LLM provider used for this run">
          <span>{providerLabel}</span>
        </Chip>
      ) : null}
    </div>
  );
}

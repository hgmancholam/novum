/**
 * SourcesCard organism — styled card for the list of evidence sources
 * collected during a run (EvidenceAdded events, RF-04).
 *
 * Shows each unique source as a row with: number, title (external link),
 * source-type badge (Tavily | Wikipedia), polarity indicator, and confidence.
 * Sorted by confidence descending so the strongest evidence appears first.
 */

import { ExternalLink, BookOpen, Globe } from "lucide-react";

import { Badge } from "@/components/atoms/Badge";
import { cn } from "@/lib/cn";
import type { EvidencePolarity, SourceType } from "@/types/events";

export interface SourceEntry {
  url: string;
  title: string;
  sourceType: SourceType;
  polarity: EvidencePolarity;
  confidence: number;
}

export interface SourcesCardProps {
  sources: readonly SourceEntry[];
  className?: string | undefined;
}

// ---- helpers ----------------------------------------------------------------

function polarityBadgeVariant(
  polarity: EvidencePolarity
): "success" | "error" | "secondary" {
  switch (polarity) {
    case "supports":
      return "success";
    case "contradicts":
      return "error";
    default:
      return "secondary";
  }
}

function polarityLabel(polarity: EvidencePolarity): string {
  switch (polarity) {
    case "supports":
      return "Supports";
    case "contradicts":
      return "Contradicts";
    default:
      return "Neutral";
  }
}

function SourceTypeIcon({ sourceType }: { sourceType: SourceType }) {
  if (sourceType === "wikipedia") {
    return (
      <BookOpen
        aria-label="Wikipedia"
        className="size-3.5 shrink-0 text-(--text-muted)"
      />
    );
  }
  return (
    <Globe
      aria-label="Web"
      className="size-3.5 shrink-0 text-(--text-muted)"
    />
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div
      role="progressbar"
      aria-label={`Confidence ${pct}%`}
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      title={`${pct}%`}
      className="relative h-1.5 w-16 overflow-hidden rounded-full bg-(--bg-tertiary)"
    >
      <div
        className="absolute inset-y-0 left-0 rounded-full bg-(--accent)"
        style={{ width: `${pct.toString()}%` }}
      />
    </div>
  );
}

// ---- component --------------------------------------------------------------

export function SourcesCard({ sources, className }: SourcesCardProps) {
  if (sources.length === 0) {
    return null;
  }

  const sorted = [...sources].sort((a, b) => b.confidence - a.confidence);

  return (
    <section
      data-testid="sources-card"
      aria-labelledby="sources-card-title"
      className={cn(
        "rounded-md border border-(--glass-border)",
        "bg-(--bg-secondary)",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-(--glass-border) px-5 py-3">
        <BookOpen
          aria-hidden="true"
          className="size-4 text-(--accent)"
        />
        <h3
          id="sources-card-title"
          className="text-sm font-semibold text-(--text-primary)"
        >
          Sources
        </h3>
        <span className="ml-auto rounded-full bg-(--bg-tertiary) px-2 py-0.5 text-xs text-(--text-muted)">
          {sources.length}
        </span>
      </div>

      {/* Source rows */}
      <ol className="divide-y divide-(--glass-border)">
        {sorted.map((src, idx) => {
          const hostname = (() => {
            try {
              return new URL(src.url).hostname.replace(/^www\./, "");
            } catch {
              return src.url;
            }
          })();

          return (
            <li
              key={src.url}
              data-testid="source-row"
              className="group flex items-start gap-3 px-5 py-3 transition-colors hover:bg-(--glass-hover)"
            >
              {/* Index */}
              <span
                aria-hidden="true"
                className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-(--bg-tertiary) text-[10px] font-semibold text-(--text-muted)"
              >
                {idx + 1}
              </span>

              {/* Main content */}
              <div className="min-w-0 flex-1">
                {/* Title row */}
                <div className="flex items-start gap-2">
                  <SourceTypeIcon sourceType={src.sourceType} />
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="line-clamp-2 text-sm font-medium text-(--text-primary) underline-offset-2 hover:text-(--accent) hover:underline"
                  >
                    {src.title}
                  </a>
                  <ExternalLink
                    aria-hidden="true"
                    className="mt-0.5 size-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-60"
                  />
                </div>

                {/* Meta row */}
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  <span className="truncate text-xs text-(--text-muted)">
                    {hostname}
                  </span>
                  <Badge
                    variant={polarityBadgeVariant(src.polarity)}
                    className="text-[10px]"
                  >
                    {polarityLabel(src.polarity)}
                  </Badge>
                  <ConfidenceBar value={src.confidence} />
                  <span className="text-[10px] text-(--text-muted)">
                    {Math.round(src.confidence * 100)}%
                  </span>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

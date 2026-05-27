/**
 * StructuredAnswer organism — renders the final answer markdown (BRD-16 §4.10, RF-10).
 *
 * Accepts pre-rendered markdown content (prose or structured) from the
 * backend renderer and displays it using ReactMarkdown.
 */
import ReactMarkdown from "react-markdown";

import { cn } from "@/lib/cn";
import type { OutputFormat } from "@/types/events";

export interface StructuredAnswerProps {
  content: string;
  outputFormat: OutputFormat;
  metadata?:
    | {
        sections?: number | undefined;
        source_count?: number | undefined;
        word_count?: number | undefined;
      }
    | undefined;
  className?: string | undefined;
}

export function StructuredAnswer({
  content,
  outputFormat,
  metadata,
  className,
}: StructuredAnswerProps) {
  const hasMetadata =
    metadata !== undefined &&
    (metadata.sections !== undefined ||
      metadata.source_count !== undefined ||
      metadata.word_count !== undefined);

  return (
    <section
      data-testid="structured-answer"
      aria-label={`Answer (${outputFormat} format)`}
      className={cn(
        "rounded-[var(--radius-md)] border border-[var(--glass-border)]",
        "bg-[var(--bg-secondary)] p-5",
        className
      )}
    >
      {hasMetadata && metadata !== undefined ? (
        <div
          data-testid="answer-metadata"
          className="mb-3 flex gap-4 text-xs text-[var(--text-muted)]"
        >
          {metadata.sections !== undefined && (
            <span>{metadata.sections} sections</span>
          )}
          {metadata.source_count !== undefined && (
            <span>{metadata.source_count} sources</span>
          )}
          {metadata.word_count !== undefined && (
            <span>{metadata.word_count} words</span>
          )}
        </div>
      ) : null}

      <div
        data-testid="answer-content"
        className="prose prose-sm prose-gray max-w-none
          prose-headings:text-[var(--text-primary)]
          prose-p:text-[var(--text-primary)]
          prose-li:text-[var(--text-primary)]
          prose-a:text-[var(--accent-primary)]"
      >
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    </section>
  );
}

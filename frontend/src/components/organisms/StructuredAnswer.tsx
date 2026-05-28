/**
 * StructuredAnswer organism — renders the final answer markdown (BRD-16 §4.10, RF-10).
 *
 * Accepts pre-rendered markdown content (prose or structured) from the
 * backend renderer and displays it using ReactMarkdown with:
 * - Mermaid diagram blocks rendered as styled code (syntax-highlighted)
 * - Markdown tables rendered natively
 * - Standard prose rendering for all other content
 *
 * IP-24 Phase 3.5: Supports optional typewriter animation via `animate` prop.
 */
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/cn";
import { useTypewriter } from "@/lib/useTypewriter";
import { BlinkingCursor } from "@/components/atoms";
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
  /** IP-24 Phase 3.5: Enable typewriter animation (default false). */
  animate?: boolean;
  /** Fires when the typewriter finishes revealing the answer. */
  onAnimationComplete?: (() => void) | undefined;
  className?: string | undefined;
}

/** Custom code-block renderer: mermaid → blue-accented fence; others → syntax highlighted. */
function CodeBlock({
  className,
  children,
}: {
  className?: string | undefined;
  children?: React.ReactNode | undefined;
}) {
  const language = /language-(\w+)/.exec(className ?? "")?.[1] ?? "";
  const code = String(children ?? "").trim();

  if (language === "mermaid") {
    return (
      <div
        data-testid="mermaid-block"
        className="my-3 overflow-x-auto rounded-lg border border-[var(--accent-primary)] bg-[var(--bg-primary)] p-4"
      >
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--accent-primary)]">
          Diagram
        </p>
        <SyntaxHighlighter
          language="yaml"
          style={oneDark}
          customStyle={{ margin: 0, borderRadius: "0.375rem", fontSize: "0.8rem" }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    );
  }

  if (language) {
    return (
      <SyntaxHighlighter
        language={language}
        style={oneDark}
        customStyle={{ borderRadius: "0.375rem", fontSize: "0.8rem" }}
      >
        {code}
      </SyntaxHighlighter>
    );
  }

  return (
    <code className="rounded bg-[var(--bg-tertiary)] px-1.5 py-0.5 font-mono text-sm text-[var(--text-primary)]">
      {children}
    </code>
  );
}

export function StructuredAnswer({
  content,
  outputFormat,
  metadata,
  animate = false,
  onAnimationComplete,
  className,
}: StructuredAnswerProps) {
  const { displayed, isTyping, skip } = useTypewriter({
    text: content,
    enabled: animate,
    onComplete: onAnimationComplete,
  });

  const hasMetadata =
    metadata !== undefined &&
    (metadata.sections !== undefined ||
      metadata.source_count !== undefined ||
      metadata.word_count !== undefined);

  function handleSkip(
    e:
      | React.MouseEvent<HTMLDivElement>
      | React.KeyboardEvent<HTMLDivElement>
  ): void {
    if (isTyping) {
      e.stopPropagation();
      skip();
    }
  }

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
          prose-a:text-[var(--accent-primary)]
          prose-table:text-[var(--text-primary)]
          prose-th:text-[var(--text-primary)]
          prose-td:text-[var(--text-primary)]"
        role="button"
        tabIndex={isTyping ? 0 : -1}
        onClick={handleSkip}
        onKeyDown={(e) => {
          if (isTyping && (e.key === "Escape" || e.key === " ")) {
            handleSkip(e);
          }
        }}
        style={{ cursor: isTyping ? "pointer" : "default" }}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            code: CodeBlock as any,
          }}
        >
          {displayed}
        </ReactMarkdown>
        {isTyping ? <BlinkingCursor /> : null}
      </div>
    </section>
  );
}

/**
 * AnswerToolbar molecule — top-right controls inside the run-answer card.
 *
 * Surfaces:
 *   - Copy plain text (lucide `Copy`)
 *   - Copy as Markdown (lucide `Code`, the "</>" pattern)
 *   - Prose / Structured view toggle (only when both renderings are available)
 *
 * Pure presentational: parent passes the raw payloads + the current view mode.
 */

import { Check, Code, Copy } from "lucide-react";
import { useCallback, useState } from "react";

import { cn } from "@/lib/cn";
import { copyToClipboard } from "@/lib/clipboard";
import { useToastStore } from "@/stores/toastStore";

export type AnswerViewMode = "prose" | "structured";

export interface AnswerToolbarProps {
  /** Raw markdown source (always the authoritative copy). */
  markdownSource: string;
  /** Plain-text rendering for the "Copy" button. Defaults to `markdownSource`. */
  plainText?: string | undefined;
  /** Current view mode — controls which toggle button is `aria-pressed`. */
  viewMode: AnswerViewMode;
  /** Called when the user picks a different view mode. When omitted, the toggle is hidden. */
  onViewModeChange?: ((mode: AnswerViewMode) => void) | undefined;
  /** Hide the toggle even when `onViewModeChange` is provided (e.g. no structured render available). */
  showToggle?: boolean | undefined;
  className?: string | undefined;
}

const COPY_FEEDBACK_MS = 1500;

function IconButton({
  label,
  onClick,
  copied,
  Icon,
}: {
  label: string;
  onClick: () => void;
  copied: boolean;
  Icon: typeof Copy;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex h-8 w-8 items-center justify-center rounded-md",
        "border border-(--glass-border) bg-(--glass-bg) text-(--text-secondary)",
        "transition-colors hover:bg-(--glass-hover) hover:text-(--text-primary)",
        "focus-visible:outline-2 focus-visible:outline-(color:--accent) focus-visible:outline-offset-2",
      )}
    >
      {copied ? (
        <Check aria-hidden="true" className="h-4 w-4 text-(--semantic-success)" />
      ) : (
        <Icon aria-hidden="true" className="h-4 w-4" />
      )}
    </button>
  );
}

export function AnswerToolbar({
  markdownSource,
  plainText,
  viewMode,
  onViewModeChange,
  showToggle = true,
  className,
}: AnswerToolbarProps) {
  const push = useToastStore((s) => s.push);
  const [copiedText, setCopiedText] = useState(false);
  const [copiedMarkdown, setCopiedMarkdown] = useState(false);

  const handleCopy = useCallback(
    async (
      payload: string,
      successMsg: string,
      setLocal: (v: boolean) => void,
    ) => {
      try {
        await copyToClipboard(payload);
        setLocal(true);
        push({ kind: "success", message: successMsg });
        setTimeout(() => {
          setLocal(false);
        }, COPY_FEEDBACK_MS);
      } catch {
        push({ kind: "error", message: "Could not copy to clipboard" });
      }
    },
    [push],
  );

  const handleCopyText = useCallback(() => {
    void handleCopy(plainText ?? markdownSource, "Answer copied", setCopiedText);
  }, [handleCopy, markdownSource, plainText]);

  const handleCopyMarkdown = useCallback(() => {
    void handleCopy(markdownSource, "Markdown copied", setCopiedMarkdown);
  }, [handleCopy, markdownSource]);

  const toggleVisible = showToggle && onViewModeChange !== undefined;

  return (
    <div
      data-testid="answer-toolbar"
      className={cn(
        "flex items-center gap-2",
        className,
      )}
    >
      {toggleVisible ? (
        <div
          role="group"
          aria-label="Answer view format"
          className={cn(
            "inline-flex overflow-hidden rounded-md border border-(--glass-border)",
            "bg-(--glass-bg) text-xs",
          )}
        >
          {(["prose", "structured"] as const).map((mode) => {
            const active = viewMode === mode;
            return (
              <button
                key={mode}
                type="button"
                onClick={() => {
                  onViewModeChange(mode);
                }}
                aria-pressed={active}
                className={cn(
                  "px-3 py-1 capitalize transition-colors",
                  "focus-visible:outline-2 focus-visible:outline-(color:--accent) focus-visible:outline-offset-(-2px)",
                  active
                    ? "bg-(--accent-soft) text-(--text-primary)"
                    : "text-(--text-secondary) hover:bg-(--glass-hover) hover:text-(--text-primary)",
                )}
              >
                {mode === "prose" ? "Prose" : "Structured"}
              </button>
            );
          })}
        </div>
      ) : null}
      <IconButton
        label="Copy answer"
        onClick={handleCopyText}
        copied={copiedText}
        Icon={Copy}
      />
      <IconButton
        label="Copy as Markdown"
        onClick={handleCopyMarkdown}
        copied={copiedMarkdown}
        Icon={Code}
      />
    </div>
  );
}

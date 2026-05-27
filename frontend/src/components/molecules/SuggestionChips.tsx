/**
 * SuggestionChips molecule — first-run onboarding (RF-06).
 * 3 chips, each fills the question textarea (does NOT submit). See §7.7.
 */

import { cn } from "@/lib/cn";

export interface SuggestionChipsProps {
  onPick: (question: string) => void;
  className?: string | undefined;
}

export const DEFAULT_SUGGESTIONS: readonly string[] = [
  "What is event sourcing?",
  "React vs Vue for a team of 5",
  "Best framework for LLM agents in 2026",
] as const;

export function SuggestionChips({ onPick, className }: SuggestionChipsProps) {
  return (
    <div
      data-testid="suggestion-chips"
      className={cn("flex flex-col gap-2", className)}
    >
      <p className="text-xs text-[var(--text-secondary)]">Try one of these:</p>
      <div className="flex flex-wrap gap-2">
        {DEFAULT_SUGGESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => {
              onPick(q);
            }}
            className={cn(
              "rounded-[var(--radius-sm)] border border-[var(--glass-border)]",
              "bg-[var(--bg-tertiary)] px-3 py-1.5 text-xs",
              "text-[var(--text-primary)] transition-colors duration-150",
              "hover:bg-[var(--glass-bg)]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
            )}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

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
      <p className="text-xs text-(--text-secondary)">Try one of these:</p>
      <div className="flex flex-wrap gap-2">
        {DEFAULT_SUGGESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => {
              onPick(q);
            }}
            className={cn(
              "inline-flex items-center gap-2 rounded-full",
              "border border-(--glass-border) bg-(--glass-bg) backdrop-blur",
              "px-3 py-1 text-xs text-(--text-secondary)",
              "transition-colors hover:bg-(--glass-hover) hover:text-(--text-primary)",
              "focus-visible:outline-2 focus-visible:outline-(color:--accent) focus-visible:outline-offset-2"
            )}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

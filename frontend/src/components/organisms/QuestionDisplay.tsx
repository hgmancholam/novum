/**
 * QuestionDisplay organism — renders the user's question (C2).
 * See ui-prototype.md §3.1 (C2) and BRD-13 §4.3.
 * Pure presentational. Tokens only.
 */

import { cn } from "@/lib/cn";

export interface QuestionDisplayProps {
  question: string;
  className?: string | undefined;
}

export function QuestionDisplay({ question, className }: QuestionDisplayProps) {
  return (
    <div
      data-testid="question-display"
      className={cn("mx-auto w-full max-w-3xl", className)}
    >
      <h1 className="text-2xl font-semibold leading-snug text-[var(--text-primary)]">
        {question}
      </h1>
    </div>
  );
}

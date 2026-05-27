/**
 * JumpToLatestPill atom — floating pill shown when the trace timeline is
 * not sticky-at-bottom. Microcopy is verbatim from ui-prototype.md §7.
 */

import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/cn";

export interface JumpToLatestPillProps {
  onClick: () => void;
  className?: string | undefined;
}

export function JumpToLatestPill({ onClick, className }: JumpToLatestPillProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid="jump-to-latest-pill"
      aria-label="Jump to latest"
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs",
        "border border-[var(--glass-border)] bg-[var(--glass-bg)]",
        "text-[var(--accent)]",
        "backdrop-blur-[20px] backdrop-saturate-[180%]",
        "shadow-md hover:bg-[var(--bg-tertiary)]",
        "transition-colors",
        className
      )}
    >
      <span>Jump to latest</span>
      <ChevronDown aria-hidden="true" width={14} height={14} />
    </button>
  );
}

/**
 * LineageBadge molecule — IP-15.
 *
 * Renders a small badge that links back to the parent run when the current
 * run was forked (RF-03). Hidden entirely when `parentRunId` is null.
 *
 * Atoms-only deps (Badge); pure presentational.
 */

import { Link } from "react-router-dom";

import { Badge } from "@/components/atoms";
import { cn } from "@/lib/cn";
import { LINEAGE_BADGE_LABEL } from "@/lib/microcopy";

export interface LineageBadgeProps {
  parentRunId: string | null;
  className?: string | undefined;
}

export function LineageBadge({ parentRunId, className }: LineageBadgeProps) {
  if (parentRunId === null) {
    return null;
  }

  return (
    <Link
      to={`/runs/${parentRunId}`}
      data-testid="lineage-badge"
      data-parent-run-id={parentRunId}
      aria-label={`${LINEAGE_BADGE_LABEL} — open parent run`}
      className={cn(
        "inline-flex no-underline hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] rounded-full",
        className
      )}
    >
      <Badge variant="info">
        <span aria-hidden="true" className="mr-1">
          ↩
        </span>
        {LINEAGE_BADGE_LABEL}
      </Badge>
    </Link>
  );
}

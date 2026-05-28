/**
 * PlanStepCard molecule — display for PlanCreated / PlanRevised events.
 * IP-24 Phase 2.
 */

import { useState } from "react";
import { CheckCircle2, Circle, MinusCircle } from "lucide-react";
import { FeedStep } from "./FeedStep";
import { Badge, CollapseToggleButton } from "@/components/atoms";
import { cn } from "@/lib/cn";

export interface SubClaim {
  id: string;
  text: string;
  status: "pending" | "covered" | "uncoverable";
}

export interface PlanStepCardProps {
  rationale: string;
  subClaims: readonly SubClaim[];
  complexityHint?: string | undefined;
  isActive?: boolean | undefined;
  deltaMs?: number | undefined;
  isRevision?: boolean;
  className?: string | undefined;
}

const STATUS_ICONS = {
  covered: CheckCircle2,
  uncoverable: MinusCircle,
  pending: Circle,
} as const;

const STATUS_COLORS = {
  covered: "text-[var(--semantic-success)]",
  uncoverable: "text-[var(--semantic-warning)]",
  pending: "text-[var(--text-muted)]",
} as const;

export function PlanStepCard({
  rationale,
  subClaims,
  complexityHint,
  isActive = false,
  deltaMs,
  isRevision = false,
  className,
}: PlanStepCardProps) {
  const [isRationaleExpanded, setIsRationaleExpanded] = useState(false);

  const title = isRevision ? "Revised the plan" : "Drafted a plan";
  const shouldTruncate = rationale.length > 160;

  return (
    <FeedStep
      type={isRevision ? "PlanRevised" : "PlanCreated"}
      title={title}
      isActive={isActive}
      deltaMs={deltaMs}
      className={className}
    >
      {complexityHint ? (
        <div className="mb-2">
          <Badge variant="secondary" className="text-xs">
            {complexityHint}
          </Badge>
        </div>
      ) : null}

      <div className="mb-3">
        <div className="flex items-center justify-between gap-2 mb-1">
          <span className="text-xs text-[var(--text-muted)]">Rationale</span>
          {shouldTruncate ? (
            <CollapseToggleButton
              isCollapsed={!isRationaleExpanded}
              onToggle={() => {
                setIsRationaleExpanded(!isRationaleExpanded);
              }}
              labelCollapse="Collapse rationale"
              labelExpand="Expand rationale"
            />
          ) : null}
        </div>
        <p
          className={cn(
            "text-sm text-[var(--text-secondary)]",
            shouldTruncate && !isRationaleExpanded && "line-clamp-2"
          )}
        >
          {rationale}
        </p>
      </div>

      {subClaims.length > 0 ? (
        <div>
          <span className="text-xs text-[var(--text-muted)] block mb-2">
            Sub-claims
          </span>
          <ul className="flex flex-col gap-2">
            {subClaims.map((claim) => {
              const StatusIcon = STATUS_ICONS[claim.status];
              const colorClass = STATUS_COLORS[claim.status];
              return (
                <li key={claim.id} className="flex items-start gap-2">
                  <StatusIcon
                    aria-hidden="true"
                    width={16}
                    height={16}
                    className={cn("flex-shrink-0 mt-0.5", colorClass)}
                  />
                  <span className="text-sm text-[var(--text-secondary)]">
                    {claim.text}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </FeedStep>
  );
}

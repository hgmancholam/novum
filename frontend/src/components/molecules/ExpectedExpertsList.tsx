/**
 * ExpectedExpertsList molecule — displays expected expert types for the
 * current plan as formatted badges. See BRD-22 §4.7 and US-22-3 TC-11.
 */

import { Badge } from "@/components/atoms/Badge";

export interface ExpectedExpertsListProps {
  experts: string[];
}

function formatExpertLabel(s: string): string {
  return s
    .split("_")
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(" ");
}

export function ExpectedExpertsList({ experts }: ExpectedExpertsListProps) {
  if (experts.length === 0) {
    return null;
  }

  return (
    <div className="space-y-1.5">
      <span className="text-xs font-medium text-[var(--text-secondary)]">
        Looking for sources from:
      </span>
      <ul
        role="list"
        aria-label="Expected expert types for this plan"
        className="flex flex-wrap gap-1.5"
      >
        {experts.map((expert) => (
          <li key={expert}>
            <Badge variant="info">{formatExpertLabel(expert)}</Badge>
          </li>
        ))}
      </ul>
    </div>
  );
}

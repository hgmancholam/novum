/**
 * ComplexityBadge molecule — displays question complexity hint with
 * semantic coloring. See BRD-22 §4.4 and US-22-1 TC-08.
 */

import { Badge } from "@/components/atoms/Badge";
import type { ComplexityHint } from "@/types/events";

export interface ComplexityBadgeProps {
  hint: ComplexityHint;
}

const COMPLEXITY_CONFIG: Record<
  ComplexityHint,
  { variant: "secondary" | "default" | "info"; label: string }
> = {
  trivial: { variant: "secondary", label: "Quick lookup" },
  standard: { variant: "default", label: "Standard research" },
  deep: { variant: "info", label: "Deep investigation" },
};

export function ComplexityBadge({ hint }: ComplexityBadgeProps) {
  const config = COMPLEXITY_CONFIG[hint];

  return (
    <span role="status" aria-label={config.label}>
      <Badge variant={config.variant}>{config.label}</Badge>
    </span>
  );
}

/**
 * TemporalSensitivityBadge molecule — displays the run's temporal-sensitivity
 * bucket (BRD-23 WP-1, RF-13). Aligned with ComplexityBadge styling.
 */

import { Badge } from "@/components/atoms/Badge";
import type { TemporalSensitivity } from "@/types/events";

export interface TemporalSensitivityBadgeProps {
  sensitivity: TemporalSensitivity;
}

const TEMPORAL_CONFIG: Record<
  TemporalSensitivity,
  { variant: "secondary" | "default" | "info" | "warning"; label: string }
> = {
  static: { variant: "secondary", label: "Static topic" },
  slow_changing: { variant: "default", label: "Slow-changing" },
  volatile: { variant: "info", label: "Volatile — recency matters" },
  realtime: { variant: "warning", label: "Real-time topic" },
};

export function TemporalSensitivityBadge({ sensitivity }: TemporalSensitivityBadgeProps) {
  const config = TEMPORAL_CONFIG[sensitivity] ?? TEMPORAL_CONFIG.slow_changing;
  return (
    <span role="status" aria-label={config.label}>
      <Badge variant={config.variant}>{config.label}</Badge>
    </span>
  );
}

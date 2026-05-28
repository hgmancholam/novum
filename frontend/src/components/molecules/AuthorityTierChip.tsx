/**
 * AuthorityTierChip molecule — displays the source authority tier
 * (BRD-23 WP-3, §4.7). Rendered next to each citation in SourcesCard.
 */

import { Badge } from "@/components/atoms/Badge";
import type { AuthorityTier } from "@/types/events";

export interface AuthorityTierChipProps {
  tier: AuthorityTier;
}

const TIER_CONFIG: Record<
  AuthorityTier,
  { variant: "success" | "default" | "secondary" | "error"; label: string }
> = {
  primary_authoritative: { variant: "success", label: "Primary" },
  reputable_secondary: { variant: "default", label: "Reputable" },
  general: { variant: "secondary", label: "General" },
  low_signal: { variant: "error", label: "Low signal" },
};

export function AuthorityTierChip({ tier }: AuthorityTierChipProps) {
  const config = TIER_CONFIG[tier] ?? TIER_CONFIG.general;
  return (
    <span role="status" aria-label={config.label}>
      <Badge variant={config.variant}>{config.label}</Badge>
    </span>
  );
}

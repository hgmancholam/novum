/**
 * KpiCard atom — a single labeled metric tile (label + value + optional sub).
 */

import type { ReactNode } from "react";
import { GlassSurface } from "./GlassSurface";
import { cn } from "@/lib/cn";

export interface KpiCardProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  icon?: ReactNode;
  className?: string;
  testId?: string;
}

export function KpiCard({
  label,
  value,
  sub,
  icon,
  className,
  testId,
}: KpiCardProps) {
  return (
    <GlassSurface
      variant="default"
      elevation="sm"
      radius="lg"
      className={cn("flex flex-col gap-1 p-4", className)}
      data-testid={testId ?? "kpi-card"}
    >
      <div className="flex items-center justify-between text-xs uppercase tracking-wide text-(--text-secondary)">
        <span>{label}</span>
        {icon !== undefined ? (
          <span aria-hidden className="text-(--accent)">
            {icon}
          </span>
        ) : null}
      </div>
      <div className="text-2xl font-semibold text-(--text-primary)">{value}</div>
      {sub !== undefined ? (
        <div className="text-xs text-(--text-secondary)">{sub}</div>
      ) : null}
    </GlassSurface>
  );
}

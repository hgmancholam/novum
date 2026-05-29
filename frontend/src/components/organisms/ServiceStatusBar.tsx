/**
 * ServiceStatusBar organism — slim footer bar with one pill per upstream service
 * (BRD-27 §4.7). Mounted once at the shell level and polled every 60 s by
 * `useServiceHealth`. Failures are silent; the bar keeps the last known
 * snapshot so the UI never flashes empty.
 */

import { useMemo } from "react";

import { ServiceStatusDot } from "@/components/atoms/ServiceStatusDot";
import { ServiceStatusPill } from "@/components/molecules/ServiceStatusPill";
import { useServiceHealth } from "@/hooks/useServiceHealth";
import { cn } from "@/lib/cn";
import type { ServiceCategory, ServiceHealth } from "@/types/health";

const CATEGORY_ORDER: readonly ServiceCategory[] = [
  "llm",
  "search",
  "knowledge",
  "storage",
] as const;

const SKELETON_DOT_COUNT = 9;

function groupByCategory(
  services: readonly ServiceHealth[],
): Map<ServiceCategory, ServiceHealth[]> {
  const out = new Map<ServiceCategory, ServiceHealth[]>();
  for (const cat of CATEGORY_ORDER) {
    out.set(cat, []);
  }
  for (const svc of services) {
    out.get(svc.category)?.push(svc);
  }
  return out;
}

export interface ServiceStatusBarProps {
  className?: string;
}

export function ServiceStatusBar({ className }: ServiceStatusBarProps) {
  const { data, isLoading } = useServiceHealth();

  const grouped = useMemo(
    () => (data ? groupByCategory(data.services) : null),
    [data],
  );

  return (
    <footer
      aria-live="polite"
      aria-label="Service health"
      data-testid="service-status-bar"
      className={cn(
        "flex h-7 w-full shrink-0 items-center gap-3 overflow-x-auto",
        "border-t border-(--glass-border) bg-(--bg-secondary)/40 px-3",
        "backdrop-blur-xl text-(--text-secondary)",
        className,
      )}
    >
      {isLoading || !grouped ? (
        <div
          aria-hidden="true"
          data-testid="service-status-bar-skeleton"
          className="flex items-center gap-2"
        >
          {Array.from({ length: SKELETON_DOT_COUNT }).map((_, i) => (
            <ServiceStatusDot key={i} status="disabled" />
          ))}
        </div>
      ) : (
        CATEGORY_ORDER.flatMap((cat, catIdx) => {
          const services = grouped.get(cat) ?? [];
          if (services.length === 0) return [];
          const nodes = services.map((svc, idx) => (
            <span key={svc.id} className="inline-flex items-center gap-3">
              <ServiceStatusPill service={svc} />
              {idx < services.length - 1 ? (
                <span
                  aria-hidden="true"
                  className="text-(--text-tertiary)/60"
                >
                  ·
                </span>
              ) : null}
            </span>
          ));
          if (catIdx < CATEGORY_ORDER.length - 1) {
            nodes.push(
              <span
                key={`sep-${cat}`}
                aria-hidden="true"
                className="px-1 text-(--text-tertiary)/40"
              >
                |
              </span>,
            );
          }
          return nodes;
        })
      )}
    </footer>
  );
}

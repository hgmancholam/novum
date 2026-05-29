/**
 * ServiceStatusBar organism — slim footer bar with one pill per upstream service
 * (BRD-27 §4.7). Mounted via RunShell layout only on /run and /runs/:runId.
 * Polled every 60 s by `useServiceHealth`. Failures are silent; the bar keeps
 * the last known snapshot so the UI never flashes empty.
 */

import { Fragment, useMemo } from "react";
import {
  BrainCircuit,
  Globe,
  BookOpen,
  Database,
  type LucideProps,
} from "lucide-react";

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

const CATEGORY_ICONS: Record<
  ServiceCategory,
  React.ComponentType<LucideProps>
> = {
  llm: BrainCircuit,
  search: Globe,
  knowledge: BookOpen,
  storage: Database,
};

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
        <>
          {CATEGORY_ORDER.map((cat, catIdx) => {
            const services = grouped.get(cat) ?? [];
            if (services.length === 0) return null;
            const Icon = CATEGORY_ICONS[cat];
            return (
              <Fragment key={cat}>
                {catIdx > 0 && (
                  <span
                    aria-hidden="true"
                    className="px-0.5 text-(--text-tertiary)/40"
                  >
                    |
                  </span>
                )}
                <span className="inline-flex items-center gap-1.5">
                  <Icon
                    aria-hidden="true"
                    className="h-3 w-3 shrink-0 text-(--text-tertiary)"
                  />
                  {services.map((svc, idx) => (
                    <span
                      key={svc.id}
                      className="inline-flex items-center gap-1.5"
                    >
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
                  ))}
                </span>
              </Fragment>
            );
          })}
          <span
            aria-hidden="true"
            className="ml-auto shrink-0 text-[10px] tracking-wide text-(--text-tertiary)/50"
          >
            External services Health
          </span>
        </>
      )}
    </footer>
  );
}

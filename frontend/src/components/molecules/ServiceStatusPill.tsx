/**
 * ServiceStatusPill molecule — dot + service name + tooltip (BRD-27 §4.7).
 *
 * Hover/focus shows the native browser tooltip via `title`; the same text is
 * exposed to assistive tech via `aria-label`. Microcopy is matched to the IP-27
 * AC-04 specification.
 */

import type { HTMLAttributes } from "react";

import { ServiceStatusDot } from "@/components/atoms/ServiceStatusDot";
import { cn } from "@/lib/cn";
import type { ServiceHealth } from "@/types/health";

export interface ServiceStatusPillProps
  extends HTMLAttributes<HTMLSpanElement> {
  service: ServiceHealth;
}

function buildLabel(svc: ServiceHealth): string {
  const head = `${svc.name}: ${svc.status}`;
  if (svc.status === "ok" || svc.status === "degraded") {
    if (typeof svc.latency_ms === "number") {
      return `${head}, ${String(svc.latency_ms)}ms`;
    }
  }
  if (svc.message) {
    return `${head} — ${svc.message}`;
  }
  return head;
}

export function ServiceStatusPill({
  service,
  className,
  ...rest
}: ServiceStatusPillProps) {
  const label = buildLabel(service);
  return (
    <span
      role="group"
      aria-label={label}
      title={label}
      data-testid="service-status-pill"
      data-service-id={service.id}
      data-status={service.status}
      className={cn(
        "inline-flex items-center gap-1 text-[11px] leading-none text-(--text-secondary)",
        className,
      )}
      {...rest}
    >
      <ServiceStatusDot status={service.status} />
      <span className="font-medium text-(--text-secondary)">{service.name}</span>
    </span>
  );
}

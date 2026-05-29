/**
 * ServiceStatusDot atom — single 6 px dot used by the footer health bar (BRD-27 §4.7).
 *
 * Pure presentational: takes only a `status` (and optional `degraded` motion hint).
 * Colour is driven by CSS custom properties from index.css so dark/light themes
 * inherit automatically. Animation is gated by `prefers-reduced-motion`.
 */

import { motion, useReducedMotion, type HTMLMotionProps } from "motion/react";

import { cn } from "@/lib/cn";
import type { ServiceStatus } from "@/types/health";

export interface ServiceStatusDotProps
  extends Omit<HTMLMotionProps<"span">, "color" | "animate" | "transition"> {
  status: ServiceStatus;
}

const colorByStatus: Record<ServiceStatus, string> = {
  ok: "bg-(--semantic-success)",
  degraded: "bg-(--semantic-warning)",
  down: "bg-(--semantic-danger)",
  disabled: "bg-(--semantic-neutral)",
  no_key: "bg-(--semantic-neutral)",
};

export function ServiceStatusDot({
  status,
  className,
  ...rest
}: ServiceStatusDotProps) {
  const prefersReducedMotion = useReducedMotion();
  const shouldPulse = status === "degraded" && !prefersReducedMotion;
  const motionProps: Pick<HTMLMotionProps<"span">, "animate" | "transition"> =
    shouldPulse
      ? {
          animate: { opacity: [1, 0.4, 1] },
          transition: { duration: 1.8, repeat: Infinity, ease: "easeInOut" },
        }
      : {};

  return (
    <motion.span
      aria-hidden="true"
      data-testid="service-status-dot"
      data-status={status}
      className={cn(
        "inline-block h-1.5 w-1.5 shrink-0 rounded-full",
        colorByStatus[status],
        className,
      )}
      {...motionProps}
      {...rest}
    />
  );
}

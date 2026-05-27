/**
 * Badge atom — pill primitive with semantic colors.
 * See ui-prototype.md §1.3 (color tokens) and §8.2 (atoms).
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type BadgeVariant =
  | "default"
  | "success"
  | "warning"
  | "error"
  | "info"
  | "secondary";

export interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string | undefined;
}

const variantStyles: Record<BadgeVariant, string> = {
  default:
    "glass-subtle text-[var(--text-primary)]",
  success:
    "bg-[color-mix(in_srgb,var(--semantic-success)_18%,transparent)] text-[var(--semantic-success)] border border-[color-mix(in_srgb,var(--semantic-success)_40%,transparent)]",
  warning:
    "bg-[color-mix(in_srgb,var(--semantic-warning)_18%,transparent)] text-[var(--semantic-warning)] border border-[color-mix(in_srgb,var(--semantic-warning)_40%,transparent)]",
  error:
    "bg-[color-mix(in_srgb,var(--semantic-danger)_18%,transparent)] text-[var(--semantic-danger)] border border-[color-mix(in_srgb,var(--semantic-danger)_40%,transparent)]",
  info: "bg-[color-mix(in_srgb,var(--accent)_18%,transparent)] text-[var(--accent)] border border-[color-mix(in_srgb,var(--accent)_40%,transparent)]",
  secondary:
    "bg-[var(--bg-tertiary)] text-[var(--text-secondary)] border border-[var(--glass-border)]",
};

export function Badge({
  variant = "default",
  children,
  className,
}: BadgeProps) {
  return (
    <span
      data-variant={variant}
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium leading-none",
        variantStyles[variant],
        className
      )}
    >
      {children}
    </span>
  );
}

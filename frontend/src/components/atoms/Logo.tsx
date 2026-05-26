/**
 * Logo atom — the Novum brand mark.
 * See ui-prototype.md §1.9 (iconography) and memory-bank/conventions/iconography.md.
 *
 * Concept: three discrete dots (observations) resolving into a continuous bar
 * (conclusion). Inductive method made visual.
 *
 * Monochrome via currentColor. Never apply --accent (reserved for user action).
 */

import { cn } from "@/lib/cn";

export interface LogoProps {
  /** Size in px. Mark variant is square; wordmark variant scales width ~4.4x. */
  size?: number;
  /** Show the "Novum" wordmark next to the mark. */
  withWordmark?: boolean;
  className?: string;
  /** Accessible name. Pass empty string to mark decorative. */
  title?: string;
}

export function Logo({
  size = 24,
  withWordmark = false,
  className,
  title = "Novum",
}: LogoProps) {
  const ariaProps = title
    ? { role: "img" as const, "aria-label": title }
    : { "aria-hidden": true as const };

  if (withWordmark) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 140 32"
        width={size * (140 / 32)}
        height={size}
        fill="none"
        className={cn("text-[var(--text-primary)]", className)}
        {...ariaProps}
      >
        <circle cx="6" cy="16" r="1.75" fill="currentColor" />
        <circle cx="12" cy="16" r="1.75" fill="currentColor" />
        <circle cx="18" cy="16" r="1.75" fill="currentColor" />
        <rect x="22" y="14.5" width="8" height="3" rx="1.5" fill="currentColor" />
        <text
          x="42"
          y="21"
          fontFamily="'DM Sans', system-ui, sans-serif"
          fontSize="16"
          fontWeight={500}
          letterSpacing="-0.01em"
          fill="currentColor"
        >
          Novum
        </text>
      </svg>
    );
  }

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 32 32"
      width={size}
      height={size}
      fill="none"
      className={cn("text-[var(--text-primary)]", className)}
      {...ariaProps}
    >
      <circle cx="6" cy="16" r="1.75" fill="currentColor" />
      <circle cx="12" cy="16" r="1.75" fill="currentColor" />
      <circle cx="18" cy="16" r="1.75" fill="currentColor" />
      <rect x="22" y="14.5" width="8" height="3" rx="1.5" fill="currentColor" />
    </svg>
  );
}

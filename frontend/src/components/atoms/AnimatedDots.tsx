/**
 * AnimatedDots atom — three bouncing dots used as a "thinking" indicator.
 * See organisms/ResearchingBanner. Keyframes live in index.css (novum-dot-bounce).
 */

import { cn } from "@/lib/cn";

export interface AnimatedDotsProps {
  className?: string;
  label?: string;
}

export function AnimatedDots({
  className,
  label = "Working",
}: AnimatedDotsProps) {
  return (
    <span
      role="status"
      aria-label={label}
      className={cn(
        "inline-flex items-end gap-0.5 text-[var(--text-secondary)]",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="inline-block h-1 w-1 rounded-full bg-current"
        style={{ animation: "novum-dot-bounce 1.4s infinite", animationDelay: "0ms" }}
      />
      <span
        aria-hidden="true"
        className="inline-block h-1 w-1 rounded-full bg-current"
        style={{ animation: "novum-dot-bounce 1.4s infinite", animationDelay: "150ms" }}
      />
      <span
        aria-hidden="true"
        className="inline-block h-1 w-1 rounded-full bg-current"
        style={{ animation: "novum-dot-bounce 1.4s infinite", animationDelay: "300ms" }}
      />
    </span>
  );
}

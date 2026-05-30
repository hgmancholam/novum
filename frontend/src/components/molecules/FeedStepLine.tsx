/**
 * FeedStepLine molecule — inline label + detail row used by RunFeed.
 *
 * Visual reference: `pages/HowWeWorkPage.tsx::AnatomyOfARun` — uppercase colored
 * label, plain-text detail inline, small glowing dot on a vertical rail.
 *
 * Supports an optional `useTypewriter` reveal on the detail text (only
 * applied to the latest active step).
 */

import { type ReactNode } from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/cn";
import { useTypewriter } from "@/lib/useTypewriter";

export interface FeedStepLineProps {
  label: string;
  detail: string;
  accent: string;
  deltaMs?: number | undefined;
  /** Reveal `detail` with a typewriter animation. */
  typewriter?: boolean | undefined;
  /** Optional expanded sub-content rendered under the line. */
  children?: ReactNode;
  /** Used to disable bottom spacing when last. */
  isLast?: boolean | undefined;
  className?: string | undefined;
}

export function FeedStepLine({
  label,
  detail,
  accent,
  deltaMs,
  typewriter = false,
  children,
  isLast = false,
  className,
}: FeedStepLineProps) {
  const { displayed, isTyping } = useTypewriter({
    text: detail,
    enabled: typewriter,
  });
  const shown = typewriter ? displayed : detail;

  return (
    <motion.li
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className={cn("relative", !isLast && "pb-5", className)}
      data-testid="feed-step-line"
    >
      {/* Dot on the rail */}
      <span
        aria-hidden
        className="absolute top-1.5 -left-[22px] inline-flex h-3.5 w-3.5 items-center justify-center rounded-full"
        style={{
          background: `color-mix(in srgb, ${accent} 35%, var(--bg-primary))`,
          boxShadow: `0 0 0 3px var(--bg-primary), 0 0 10px ${accent}`,
        }}
      />

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span
          className="inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
          style={{
            color: accent,
            borderColor: `color-mix(in srgb, ${accent} 45%, transparent)`,
            background: `color-mix(in srgb, ${accent} 12%, transparent)`,
          }}
        >
          {label}
        </span>
        <span className="flex-1 text-sm leading-relaxed text-[var(--text-secondary)]">
          {shown}
          {typewriter && isTyping ? (
            <span
              aria-hidden
              className="ml-0.5 inline-block h-3.5 w-[2px] translate-y-0.5 bg-[var(--text-secondary)] animate-pulse"
            />
          ) : null}
        </span>
        {deltaMs !== undefined ? (
          <span className="ml-auto text-[11px] tabular-nums text-[var(--text-muted)]">
            +{(deltaMs / 1000).toFixed(1)}s
          </span>
        ) : null}
      </div>

      {children ? <div className="mt-2 ml-0 text-sm">{children}</div> : null}
    </motion.li>
  );
}

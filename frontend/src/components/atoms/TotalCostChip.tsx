/**
 * TotalCostChip atom — clickable cost-so-far chip shown in the run header.
 * BRD-29 §4.6 / AC-06 / AC-11.
 *
 * Reuses the existing `--accent` / `--accent-soft` tokens so the chip works
 * in both dark (default) and light (BRD-28) themes without new design tokens.
 */

import { Coins } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";
import { formatTokens, formatUsd } from "@/lib/formatCost";

export interface TotalCostChipProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  totalUsd: number;
  tokens: number;
  loading?: boolean;
}

export const TotalCostChip = forwardRef<HTMLButtonElement, TotalCostChipProps>(
  (
    { totalUsd, tokens, loading = false, className, "aria-label": ariaLabelProp, ...rest },
    ref
  ) => {
    const reduced = useReducedMotion() ?? false;
    const usdText = formatUsd(totalUsd);
    const tokensText = formatTokens(tokens);
    const ariaLabel =
      ariaLabelProp ??
      `Cost so far: ${usdText}, ${tokensText} tokens. Click to open breakdown.`;

    return (
      <button
        ref={ref}
        type="button"
        data-testid="total-cost-chip"
        aria-label={ariaLabel}
        className={cn(
          "inline-flex h-7 items-center gap-1.5 rounded-md px-2",
          "bg-[color-mix(in_srgb,var(--accent)_18%,transparent)]",
          "text-[var(--accent)]",
          "hover:bg-[color-mix(in_srgb,var(--accent)_28%,transparent)]",
          "transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]",
          className
        )}
        {...rest}
      >
        <Coins className="h-3.5 w-3.5" aria-hidden="true" />
        {loading ? (
          <span
            aria-hidden="true"
            className="inline-block h-3 w-16 animate-pulse rounded bg-[var(--glass-bg)]"
          />
        ) : (
          <motion.span
            key={usdText}
            initial={reduced ? false : { opacity: 0, y: -2 }}
            animate={reduced ? { opacity: 1, y: 0 } : { opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="font-mono text-xs"
          >
            {usdText} · {tokensText}
          </motion.span>
        )}
      </button>
    );
  }
);

TotalCostChip.displayName = "TotalCostChip";

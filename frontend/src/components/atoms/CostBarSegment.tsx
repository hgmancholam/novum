/**
 * CostBarSegment atom — single slice of the stacked breakdown bar (BRD-29 §4.6).
 */

import { forwardRef, type HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export interface CostBarSegmentProps extends HTMLAttributes<HTMLDivElement> {
  provider: string;
  value: number;
  total: number;
  color: string;
}

export const CostBarSegment = forwardRef<HTMLDivElement, CostBarSegmentProps>(
  ({ provider, value, total, color, className, style, ...rest }, ref) => {
    if (total <= 0 || value <= 0) {
      return null;
    }
    const pct = Math.max(0, Math.min(100, (value / total) * 100));
    return (
      <div
        ref={ref}
        role="presentation"
        data-testid={`cost-bar-segment-${provider}`}
        className={cn(
          "h-2 first:rounded-l-full last:rounded-r-full transition-[width] duration-300 ease-out",
          className
        )}
        style={{ width: `${pct.toString()}%`, backgroundColor: color, ...style }}
        {...rest}
      />
    );
  }
);

CostBarSegment.displayName = "CostBarSegment";

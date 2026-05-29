/**
 * ChartFrame molecule — consistent glass card around a chart.
 */

import type { ReactNode } from "react";
import { GlassSurface } from "@/components/atoms";
import { cn } from "@/lib/cn";

export interface ChartFrameProps {
  title: string;
  description?: string;
  testId?: string;
  className?: string;
  children: ReactNode;
}

export function ChartFrame({
  title,
  description,
  testId,
  className,
  children,
}: ChartFrameProps) {
  return (
    <GlassSurface
      variant="default"
      elevation="sm"
      radius="lg"
      className={cn("flex flex-col gap-3 p-4", className)}
      data-testid={testId ?? "chart-frame"}
    >
      <div className="flex flex-col gap-0.5">
        <h3 className="text-sm font-medium text-(--text-primary)">{title}</h3>
        {description !== undefined ? (
          <p className="text-xs text-(--text-secondary)">{description}</p>
        ) : null}
      </div>
      <div className="flex-1">{children}</div>
    </GlassSurface>
  );
}

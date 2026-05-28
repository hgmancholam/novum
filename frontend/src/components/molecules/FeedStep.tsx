/**
 * FeedStep molecule — base layout for a single feed item.
 * IP-24 Phase 2.
 */

import type { ReactNode } from "react";
import { motion } from "motion/react";
import type { EventType } from "@/types/events";
import { cn } from "@/lib/cn";
import { FeedStepIcon } from "@/components/atoms";

export interface FeedStepProps {
  type: EventType;
  title: string;
  summary?: string | undefined;
  isActive?: boolean | undefined;
  isLast?: boolean | undefined;
  deltaMs?: number | undefined;
  children?: ReactNode;
  className?: string | undefined;
}

export function FeedStep({
  type,
  title,
  summary,
  isActive = false,
  isLast = false,
  deltaMs,
  children,
  className,
}: FeedStepProps) {
  return (
    <motion.li
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15, ease: "easeOut" }}
      data-type={type}
      data-active={isActive}
      className={cn(
        "relative flex gap-3 pl-2",
        !isLast && "pb-3",
        className
      )}
    >
      {/* Icon overlays the rail */}
      <FeedStepIcon type={type} isActive={isActive} />

      {/* Content column */}
      <div className="flex-1 min-w-0 pt-0.5">
        <div className="flex items-center justify-between gap-2 mb-1">
          <h4 className="text-sm font-medium text-[var(--text-primary)]">
            {title}
          </h4>
          {deltaMs !== undefined ? (
            <span className="text-xs text-[var(--text-muted)] tabular-nums flex-shrink-0">
              +{(deltaMs / 1000).toFixed(1)}s
            </span>
          ) : null}
        </div>
        {summary ? (
          <p className="text-sm text-[var(--text-secondary)] mb-2">{summary}</p>
        ) : null}
        {children}
      </div>
    </motion.li>
  );
}

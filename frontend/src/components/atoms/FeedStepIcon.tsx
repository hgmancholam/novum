/**
 * FeedStepIcon atom — circular badge with event icon, optionally animated.
 * IP-24 Phase 1.
 */

import type { EventType } from "@/types/events";
import { cn } from "@/lib/cn";
import { getEventVisual, TONE_COLOR } from "@/lib/eventVisuals";

export interface FeedStepIconProps {
  type: EventType;
  isActive?: boolean;
  className?: string | undefined;
}

export function FeedStepIcon({
  type,
  isActive = false,
  className,
}: FeedStepIconProps) {
  const { Icon, tone } = getEventVisual(type);
  const borderColor = TONE_COLOR[tone];

  return (
    <div
      data-type={type}
      data-active={isActive}
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-full",
        "bg-[var(--bg-tertiary)] border-2",
        "relative z-10",
        className
      )}
      style={{ borderColor }}
    >
      {isActive ? (
        <span
          aria-hidden="true"
          className="absolute inset-0 rounded-full animate-ping opacity-60"
          style={{ backgroundColor: borderColor, opacity: 0.25 }}
        />
      ) : null}
      <Icon
        aria-hidden="true"
        width={16}
        height={16}
        className={cn("relative", isActive && "animate-pulse")}
        style={{ color: borderColor }}
      />
    </div>
  );
}

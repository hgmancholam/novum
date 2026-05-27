/**
 * EventIcon atom — Lucide icon resolved from `eventVisuals.ts` for a given
 * event type. Color is bound to the tone CSS token. `aria-hidden` because
 * the surrounding `EventNode` already labels the event.
 */

import { cn } from "@/lib/cn";
import { getEventVisual, TONE_COLOR } from "@/lib/eventVisuals";

export interface EventIconProps {
  type: string;
  size?: number;
  className?: string | undefined;
}

export function EventIcon({ type, size = 16, className }: EventIconProps) {
  const visual = getEventVisual(type);
  const Icon = visual.Icon;
  return (
    <Icon
      aria-hidden="true"
      data-testid="event-icon"
      data-tone={visual.tone}
      data-event-type={type}
      width={size}
      height={size}
      className={cn("shrink-0", className)}
      style={{ color: TONE_COLOR[visual.tone] }}
    />
  );
}

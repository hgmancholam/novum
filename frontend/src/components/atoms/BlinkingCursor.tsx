/**
 * BlinkingCursor atom — simple blinking cursor for typewriter effect.
 * IP-24 Phase 1.
 */

import { cn } from "@/lib/cn";

export interface BlinkingCursorProps {
  className?: string | undefined;
}

export function BlinkingCursor({ className }: BlinkingCursorProps) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block animate-[blink_1s_ease-in-out_infinite]", className)}
    >
      ▌
    </span>
  );
}

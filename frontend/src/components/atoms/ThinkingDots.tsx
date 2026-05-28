/**
 * ThinkingDots atom — three pulsing dots used as a "still working" indicator
 * while a run is streaming. Designed to mimic the chat-app typing indicator.
 */

import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/cn";

export interface ThinkingDotsProps {
  color?: string;
  size?: number;
  className?: string | undefined;
}

export function ThinkingDots({
  color = "var(--accent)",
  size = 6,
  className,
}: ThinkingDotsProps) {
  const reduce = useReducedMotion();
  const dots = [0, 1, 2];

  return (
    <span
      role="status"
      aria-label="Thinking"
      data-testid="thinking-dots"
      className={cn("inline-flex items-center gap-1", className)}
    >
      {dots.map((i) => (
        <motion.span
          key={i}
          className="block rounded-full"
          style={{ width: size, height: size, backgroundColor: color }}
          animate={
            reduce
              ? { opacity: 0.6 }
              : { opacity: [0.25, 1, 0.25], y: [0, -2, 0] }
          }
          transition={{
            duration: 1.2,
            repeat: Infinity,
            ease: "easeInOut",
            delay: i * 0.18,
          }}
        />
      ))}
    </span>
  );
}

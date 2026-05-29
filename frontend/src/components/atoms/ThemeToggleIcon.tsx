/**
 * ThemeToggleIcon atom (IP-28).
 *
 * Renders the Sun icon when current theme is "dark" (hinting the click
 * action: switch to light) and the Moon icon when current is "light".
 * Cross-fades on theme change via Motion; gates the rotate behind
 * `useReducedMotion` for accessibility.
 */

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Moon, Sun } from "lucide-react";

import type { Theme } from "@/lib/theme";

export interface ThemeToggleIconProps {
  theme: Theme;
}

export function ThemeToggleIcon({ theme }: ThemeToggleIconProps) {
  const reducedMotion = useReducedMotion();
  const rotateFrom = reducedMotion ? 0 : -90;
  const rotateTo = reducedMotion ? 0 : 90;

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.span
        key={theme}
        data-testid={`theme-icon-${theme}`}
        initial={{ opacity: 0, rotate: rotateFrom }}
        animate={{ opacity: 1, rotate: 0 }}
        exit={{ opacity: 0, rotate: rotateTo }}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        className="inline-flex"
      >
        {theme === "dark" ? (
          <Sun className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
        ) : (
          <Moon className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
        )}
      </motion.span>
    </AnimatePresence>
  );
}

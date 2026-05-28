/**
 * BackgroundOrbs atom — Slate Aurora signature layer.
 *
 * See ui-design.md §2.9 and §11 pattern #1. Three drifting orbs
 * (indigo + violet + amber) live above the fixed `--bg-gradient`. Required
 * on every full-viewport route. `AppShell` mounts it once for authenticated
 * pages; standalone pages import this atom directly.
 *
 * Rendering rules (verbatim from §2.9):
 *   - `pointer-events-none fixed inset-0 z-0 overflow-hidden`
 *   - Each orb is `motion.div` with radial-gradient + blur(20–28px)
 *   - Reduced motion → omit `animate` (orbs remain visible but static)
 *   - Amber opacity capped at 0.10 (trust token reserve, §2.5)
 */

import { motion, useReducedMotion } from "motion/react";

export function BackgroundOrbs() {
  const reduce = useReducedMotion();
  return (
    <div
      aria-hidden
      data-testid="background-orbs"
      className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
    >
      <motion.div
        className="absolute -top-40 left-1/2 h-160 w-160 -translate-x-1/2 rounded-full"
        style={{
          background:
            "radial-gradient(closest-side, rgba(99,102,241,0.28), transparent 70%)",
          filter: "blur(20px)",
        }}
        animate={reduce ? {} : { y: [0, 18, 0] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute top-1/3 -right-32 h-105 w-105 rounded-full"
        style={{
          background:
            "radial-gradient(closest-side, rgba(168,85,247,0.18), transparent 70%)",
          filter: "blur(24px)",
        }}
        animate={reduce ? {} : { y: [0, -22, 0] }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-0 left-0 h-95 w-95 rounded-full"
        style={{
          background:
            "radial-gradient(closest-side, rgba(251,191,36,0.10), transparent 70%)",
          filter: "blur(28px)",
        }}
        animate={reduce ? {} : { y: [0, 14, 0] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}

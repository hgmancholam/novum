/**
 * Motion presets — ui-design.md §5.3 and §11 pattern #8.
 *
 * `fadeUp` + `stagger` is the canonical scroll-reveal pair used by every
 * section below the fold. Easing `[0.16, 1, 0.3, 1]` is `--ease-out`.
 */

import type { Variants } from "motion/react";

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] },
  }),
};

export const stagger: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
};

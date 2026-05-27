/**
 * GlassSurface atom — glassmorphism primitive.
 *
 * See ui-design.md §2.3 (glass surfaces), §4 (elevation), §6 (interactive
 * treatments). Encapsulates the canonical glass recipe so components stop
 * repeating `bg-[var(--glass-bg)] border border-[var(--glass-border)]
 * backdrop-blur-[20px] backdrop-saturate-[180%]` at every call site.
 *
 * Variants:
 *   - subtle:  blur 12px, 50% glass alpha — chips, inline pills
 *   - default: blur 20px, full glass     — panels, cards, modals
 *   - strong:  blur 28px, heavier border — popovers, dropdowns, overlays
 *
 * Elevation:
 *   - none | sm | md | lg | glow — maps to --shadow-* tokens (ui-design.md §4)
 *
 * Polymorphic via the `as` prop (defaults to `div`).
 */

import {
  forwardRef,
  type ElementType,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { cn } from "@/lib/cn";

export type GlassVariant = "subtle" | "default" | "strong";
export type GlassElevation = "none" | "sm" | "md" | "lg" | "glow";
export type GlassRadius = "none" | "sm" | "md" | "lg" | "xl";

export interface GlassSurfaceProps extends HTMLAttributes<HTMLElement> {
  variant?: GlassVariant;
  elevation?: GlassElevation;
  radius?: GlassRadius;
  as?: ElementType;
  className?: string | undefined;
  children?: ReactNode;
}

const variantStyles: Record<GlassVariant, string> = {
  subtle: "glass-subtle",
  default: "glass",
  strong: "glass-strong",
};

const elevationStyles: Record<GlassElevation, string> = {
  none: "",
  sm: "shadow-[var(--shadow-sm)]",
  md: "shadow-[var(--shadow-md)]",
  lg: "shadow-[var(--shadow-lg)]",
  glow: "shadow-[var(--shadow-glow)]",
};

const radiusStyles: Record<GlassRadius, string> = {
  none: "",
  sm: "rounded-[var(--radius-sm)]",
  md: "rounded-[var(--radius-md)]",
  lg: "rounded-[var(--radius-lg)]",
  xl: "rounded-[var(--radius-xl)]",
};

export const GlassSurface = forwardRef<HTMLElement, GlassSurfaceProps>(
  (
    {
      variant = "default",
      elevation = "md",
      radius = "lg",
      as,
      className,
      children,
      ...rest
    },
    ref
  ) => {
    const Component = (as ?? "div") as ElementType;
    return (
      <Component
        ref={ref}
        data-variant={variant}
        data-elevation={elevation}
        className={cn(
          variantStyles[variant],
          elevationStyles[elevation],
          radiusStyles[radius],
          className
        )}
        {...rest}
      >
        {children}
      </Component>
    );
  }
);

GlassSurface.displayName = "GlassSurface";

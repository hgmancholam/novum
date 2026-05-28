/**
 * Button atom.
 * Canonical CTA recipe — ui-design.md §6.1.1 (primary/secondary) and §11
 * pattern #4. All variants are glass: translucent fill, backdrop blur,
 * 1 px tinted border. Hierarchy lives in the tint, not the chrome.
 *
 * Sizes:
 *   - sm: compact / icon-row actions (rounded-lg, px-3 py-1.5)
 *   - md: canonical CTA (rounded-xl, px-5 py-2.5, text-sm font-medium)
 *   - lg: hero CTA (rounded-xl, px-6 py-3, text-base font-medium)
 */

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  children?: ReactNode;
}

const baseStyles =
  "group inline-flex items-center justify-center gap-2 " +
  "transition-[background-color,transform,box-shadow,opacity,color] " +
  "duration-200 ease-out " +
  "focus-visible:outline-2 " +
  "focus-visible:outline-(color:--accent) focus-visible:outline-offset-2 " +
  "disabled:pointer-events-none disabled:opacity-50";

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-(--accent) text-white font-medium shadow-(--shadow-glow) " +
    "hover:bg-(--accent-hover) hover:-translate-y-0.5 " +
    "hover:shadow-[0_12px_28px_var(--accent-glow)] " +
    "active:translate-y-0 active:scale-[0.98]",
  secondary:
    "border border-(--glass-border) bg-(--glass-bg) backdrop-blur-xl " +
    "text-(--text-secondary) " +
    "hover:bg-(--glass-hover) hover:text-(--text-primary) " +
    "active:scale-[0.98]",
  ghost:
    "bg-transparent text-(--text-primary) " +
    "hover:bg-(--glass-bg) hover:backdrop-blur-md " +
    "active:scale-[0.98]",
  danger:
    "glass-danger text-(--text-primary) font-medium " +
    "hover:bg-[color-mix(in_srgb,var(--semantic-danger)_32%,transparent)] " +
    "hover:shadow-[0_8px_24px_rgba(239,68,68,0.4)] active:scale-[0.97]",
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: "rounded-lg px-3 py-1.5 text-xs",
  md: "rounded-xl px-5 py-2.5 text-sm",
  lg: "rounded-xl px-6 py-3 text-base",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      loading = false,
      disabled,
      children,
      type = "button",
      ...rest
    },
    ref
  ) => {
    const isDisabled = disabled === true || loading;
    return (
      <button
        ref={ref}
        type={type}
        className={cn(
          baseStyles,
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        disabled={isDisabled}
        aria-busy={loading || undefined}
        {...rest}
      >
        {loading ? (
          <span
            className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent"
            aria-hidden="true"
            data-testid="button-spinner"
          />
        ) : null}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";

/**
 * Button atom.
 * See ui-design.md §6.1 (glass button variants) and §1 (glass as the
 * default surface treatment). Sizes: sm | md | lg.
 *
 * All four variants use a glass surface (translucent fill + backdrop blur +
 * 1px tinted border). Hierarchy is encoded in the tint, not in the chrome.
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
  "inline-flex items-center justify-center font-medium rounded-[12px] " +
  "transition-[background-color,transform,box-shadow,opacity] duration-150 ease-out " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 " +
  "focus-visible:ring-[var(--accent)] focus-visible:ring-offset-[var(--bg-primary)] " +
  "disabled:pointer-events-none disabled:opacity-50";

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "glass-primary text-white " +
    "hover:bg-[var(--accent-hover)] hover:shadow-[0_8px_24px_var(--accent-glow)] " +
    "active:scale-[0.97]",
  secondary:
    "glass text-[var(--text-primary)] hover:bg-[var(--glass-hover)] active:scale-[0.98]",
  ghost:
    "bg-transparent text-[var(--text-primary)] " +
    "hover:bg-[var(--glass-bg)] hover:[backdrop-filter:blur(12px)_saturate(150%)] " +
    "active:scale-[0.98]",
  danger:
    "glass-danger text-[var(--text-primary)] " +
    "hover:bg-[color-mix(in_srgb,var(--semantic-danger)_32%,transparent)] " +
    "hover:shadow-[0_8px_24px_rgba(239,68,68,0.4)] active:scale-[0.97]",
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
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
            className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent"
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

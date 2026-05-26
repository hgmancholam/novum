/**
 * Button atom.
 * See ui-prototype.md §8.2 (atoms) and §1.6 (animation policy).
 *
 * Variants follow ui-prototype.md §8.2: primary | secondary | ghost | danger.
 * Sizes: sm | md | lg.
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
  "transition-[background-color,transform,opacity] duration-150 ease-out " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 " +
  "focus-visible:ring-[var(--accent)] focus-visible:ring-offset-[var(--bg-primary)] " +
  "disabled:pointer-events-none disabled:opacity-50";

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-[var(--accent)] text-[var(--text-primary)] hover:bg-[var(--accent-hover)] active:scale-[0.97]",
  secondary:
    "bg-[var(--bg-tertiary)] text-[var(--text-primary)] hover:bg-[var(--glass-bg)] border border-[var(--glass-border)]",
  ghost:
    "bg-transparent text-[var(--text-primary)] hover:bg-[var(--glass-bg)]",
  danger:
    "bg-[var(--semantic-danger)] text-[var(--text-primary)] hover:opacity-90 active:scale-[0.97]",
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

/**
 * ThemeToggle molecule (IP-28 / BRD-28).
 *
 * 36px square button in the top action bar. role="switch" with
 * aria-checked reflecting the current theme. Native title attribute
 * provides a hover tooltip (matches ServiceStatusPill convention).
 */

import { ThemeToggleIcon } from "@/components/atoms/ThemeToggleIcon";
import { useTheme } from "@/hooks/useTheme";
import { cn } from "@/lib/cn";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const isLight = theme === "light";
  const label = isLight ? "Switch to dark mode" : "Switch to light mode";
  const tooltip = isLight ? "Dark mode" : "Light mode";

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isLight}
      aria-label={label}
      title={tooltip}
      onClick={toggle}
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-md",
        "text-(--text-primary) transition-colors",
        "hover:bg-(--glass-bg)",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--accent)"
      )}
    >
      <ThemeToggleIcon theme={theme} />
    </button>
  );
}

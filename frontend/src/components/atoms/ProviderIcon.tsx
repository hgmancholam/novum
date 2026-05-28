/**
 * ProviderIcon atom — compact visual marker for an LLM provider.
 *
 * Renders a small monochrome pill with a 2-letter brand initial styled
 * with the site's glass tokens. Used in `RunRow` (history list) and as
 * a chip in `MetaRow` (run header).
 */

import { PROVIDER_LABELS, type LlmProviderName } from "@/lib/providers";
import { cn } from "@/lib/cn";

export interface ProviderIconProps {
  /** Provider name from the backend. Unknown names render as "??". */
  name: string;
  /** Size variant — `xs` fits next to a status dot, `sm` fits in a chip row. */
  size?: "xs" | "sm";
  className?: string | undefined;
}

const INITIALS: Record<LlmProviderName, string> = {
  github: "GH",
  openai: "AI",
  anthropic: "AN",
  google: "GM",
};

function isProvider(v: string): v is LlmProviderName {
  return v in INITIALS;
}

export function ProviderIcon({ name, size = "xs", className }: ProviderIconProps) {
  const known = isProvider(name);
  const initials = known ? INITIALS[name] : "??";
  const label = known ? PROVIDER_LABELS[name] : name;
  const sizeClasses =
    size === "xs"
      ? "h-4 min-w-4 px-1 text-[9px]"
      : "h-5 min-w-5 px-1.5 text-[10px]";

  return (
    <span
      title={`Provider: ${label}`}
      aria-label={`Provider: ${label}`}
      data-testid="provider-icon"
      data-provider={name}
      className={cn(
        "glass-subtle inline-flex items-center justify-center rounded-full",
        "font-semibold uppercase tracking-tight text-(--text-secondary)",
        "border border-(--glass-border)",
        sizeClasses,
        className
      )}
    >
      {initials}
    </span>
  );
}

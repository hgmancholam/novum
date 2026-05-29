/**
 * ProviderSelect — atom that lets the user pick which LLM vendor will
 * power the upcoming run. The choice is read-only for the duration of
 * the run (server-side guarantee) and persisted in localStorage.
 *
 * Renders a native <select> for accessibility and zero dependency cost.
 */

import { type ChangeEvent } from "react";

import { cn } from "@/lib/cn";
import {
  DEFAULT_PROVIDER,
  LLM_PROVIDERS,
  PROVIDER_LABELS,
  type LlmProviderName,
} from "@/lib/providers";

export interface ProviderSelectProps {
  value: LlmProviderName;
  onChange: (next: LlmProviderName) => void;
  className?: string;
  disabled?: boolean;
}

export function ProviderSelect({
  value,
  onChange,
  className,
  disabled = false,
}: ProviderSelectProps) {
  function handleChange(e: ChangeEvent<HTMLSelectElement>) {
    const next = e.target.value as LlmProviderName;
    onChange(next);
  }

  return (
    <label
      className={cn(
        "inline-flex items-center gap-1.5 text-xs text-(--text-secondary)",
        className
      )}
    >
      <span className="select-none">Vendor:</span>
      <select
        value={value}
        onChange={handleChange}
        disabled={disabled}
        aria-label="LLM provider for this run"
        data-testid="provider-select"
        className={cn(
          "cursor-pointer rounded-sm border",
          "border-(--glass-border) bg-(--bg-tertiary) px-1.5 py-0.5",
          "text-xs text-(--text-primary)",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--accent)",
          "disabled:cursor-not-allowed disabled:opacity-50"
        )}
      >
        {LLM_PROVIDERS.map((p) => {
          const isDisabled = p !== DEFAULT_PROVIDER;
          return (
            <option key={p} value={p} disabled={isDisabled}>
              {PROVIDER_LABELS[p]}
              {isDisabled ? " (unavailable)" : ""}
            </option>
          );
        })}
      </select>
    </label>
  );
}

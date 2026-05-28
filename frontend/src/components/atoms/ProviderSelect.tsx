/**
 * ProviderSelect — atom that lets the user pick which LLM vendor will
 * power the upcoming run. The choice is read-only for the duration of
 * the run (server-side guarantee) and persisted in localStorage.
 *
 * Renders a native <select> for accessibility and zero dependency cost.
 */

import { useEffect, useState, type ChangeEvent } from "react";

import { cn } from "@/lib/cn";
import {
  DEFAULT_PROVIDER,
  LLM_PROVIDERS,
  PROVIDER_LABELS,
  fetchProviders,
  type LlmProviderName,
  type ProviderInfo,
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
  // Availability map drives the disabled state of each <option>. We don't
  // fail loudly if the fetch errors — fall back to "all enabled" so the
  // user can still pick (the backend will return 400 on submit if needed).
  const [available, setAvailable] = useState<Record<LlmProviderName, boolean>>({
    github: true,
    openai: true,
    anthropic: true,
    google: true,
  });

  useEffect(() => {
    let cancelled = false;
    fetchProviders()
      .then((res) => {
        if (cancelled) return;
        const next: Record<LlmProviderName, boolean> = {
          github: true,
          openai: true,
          anthropic: true,
          google: true,
        };
        res.providers.forEach((p: ProviderInfo) => {
          next[p.name] = p.available;
        });
        setAvailable(next);
      })
      .catch(() => {
        // Leave defaults — degraded but usable.
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
      <span className="select-none">Model:</span>
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
        {LLM_PROVIDERS.map((p) => (
          <option
            key={p}
            value={p}
            disabled={!available[p] && p !== DEFAULT_PROVIDER}
          >
            {PROVIDER_LABELS[p]}
            {!available[p] && p !== DEFAULT_PROVIDER ? " (no key)" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}

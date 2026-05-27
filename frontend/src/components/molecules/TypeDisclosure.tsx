/**
 * TypeDisclosure molecule — RF-06 supported/rejected question types.
 * Always visible in C1 below the question form. Microcopy from ui-prototype.md §7.3.
 */

import { cn } from "@/lib/cn";

export interface TypeDisclosureProps {
  className?: string | undefined;
}

interface TypeEntry {
  label: string;
  example: string;
}

const supported: readonly TypeEntry[] = [
  { label: "Factual", example: '"When was Tekton Labs founded?"' },
  { label: "Comparative", example: '"React vs Vue for a team of 5."' },
  { label: "Definitional", example: '"What is event sourcing?"' },
  {
    label: "State-of-the-art",
    example: '"Best framework for LLM agents in 2026?"',
  },
  { label: "Causal", example: '"Why did Rust gain traction in systems?"' },
] as const;

const rejected: readonly { label: string; reason: string }[] = [
  { label: "Predictive", reason: "future events Novum cannot verify" },
  { label: "Opinion", reason: "subjective preferences" },
  { label: "Personal data", reason: "individuals' private information" },
] as const;

export function TypeDisclosure({ className }: TypeDisclosureProps) {
  return (
    <section
      data-testid="type-disclosure"
      aria-labelledby="type-disclosure-title"
      className={cn(
        "glass-subtle rounded-[var(--radius-md)] p-4 text-sm",
        className
      )}
    >
      <h3
        id="type-disclosure-title"
        className="mb-3 text-sm font-medium text-[var(--text-primary)]"
      >
        What Novum answers
      </h3>
      <ul className="space-y-1">
        {supported.map((t) => (
          <li key={t.label} className="flex gap-2">
            <span
              aria-hidden="true"
              className="text-[var(--semantic-success)]"
            >
              ✓
            </span>
            <span className="font-medium text-[var(--text-primary)]">
              {t.label}
            </span>
            <span className="text-[var(--text-secondary)]">{t.example}</span>
          </li>
        ))}
      </ul>

      <h3 className="mb-2 mt-4 text-sm font-medium text-[var(--text-primary)]">
        What Novum will not answer
        <span className="ml-1 font-normal text-[var(--text-secondary)]">
          (it will tell you why)
        </span>
      </h3>
      <ul className="space-y-1">
        {rejected.map((t) => (
          <li key={t.label} className="flex gap-2">
            <span
              aria-hidden="true"
              className="text-[var(--semantic-warning)]"
            >
              ✗
            </span>
            <span className="font-medium text-[var(--text-primary)]">
              {t.label}
            </span>
            <span className="text-[var(--text-secondary)]">— {t.reason}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

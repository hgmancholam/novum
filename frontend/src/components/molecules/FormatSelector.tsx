/**
 * FormatSelector molecule — dynamic format picker (BRD-16 §4.9, RF-10).
 *
 * Fetches available formats from GET /api/formats and renders a button
 * group. Pure data-display molecule; selection state is controlled by parent.
 */
import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/cn";
import { API_URL } from "@/lib/constants";

interface Format {
  name: string;
  display: string;
}

export interface FormatSelectorProps {
  value: string;
  onChange: (format: string) => void;
  className?: string | undefined;
}

async function fetchFormats(): Promise<Format[]> {
  const response = await fetch(`${API_URL}/api/formats`);
  if (!response.ok) throw new Error("Failed to fetch formats");
  const data = (await response.json()) as { formats: Format[] };
  return data.formats;
}

export function FormatSelector({
  value,
  onChange,
  className,
}: FormatSelectorProps) {
  const { data: formats = [], isLoading } = useQuery({
    queryKey: ["formats"],
    queryFn: fetchFormats,
    staleTime: Infinity, // formats are static; no need to refetch
  });

  if (isLoading) {
    return (
      <div
        className={cn(
          "h-9 w-48 animate-pulse rounded-lg bg-[var(--bg-secondary)]",
          className
        )}
        aria-label="Loading formats"
      />
    );
  }

  return (
    <div
      role="group"
      aria-label="Output format"
      className={cn("flex gap-2", className)}
    >
      {formats.map((format) => (
        <button
          key={format.name}
          type="button"
          onClick={() => onChange(format.name)}
          aria-pressed={value === format.name}
          className={cn(
            "rounded-lg px-4 py-2 text-sm font-medium transition-colors",
            value === format.name
              ? "bg-[var(--accent-primary)] text-[var(--accent-fg)]"
              : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
          )}
        >
          {format.display}
        </button>
      ))}
    </div>
  );
}

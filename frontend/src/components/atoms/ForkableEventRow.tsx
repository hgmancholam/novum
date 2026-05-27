/**
 * ForkableEventRow atom — IP-15.
 *
 * One selectable row in the ForkModal list. Pure presentational: icon +
 * event type + summary, with a "Fork from here" call-to-action.
 *
 * Atom-only deps (EventIcon + Button + tokens). Re-uses `getEventVisual`
 * via `EventIcon` for tone-driven coloring.
 */

import { Button, EventIcon } from "@/components/atoms";
import { cn } from "@/lib/cn";

export interface ForkableEventRowProps {
  eventId: string;
  type: string;
  stepIndex: number;
  summary?: string | undefined;
  isPending?: boolean | undefined;
  onSelect: (eventId: string) => void;
  className?: string | undefined;
}

export function ForkableEventRow({
  eventId,
  type,
  stepIndex,
  summary,
  isPending = false,
  onSelect,
  className,
}: ForkableEventRowProps) {
  return (
    <li
      data-testid="forkable-event-row"
      data-event-id={eventId}
      data-event-type={type}
      className={cn(
        "flex items-center gap-3 rounded-[var(--radius-sm)] border border-[var(--glass-border)] bg-[var(--bg-tertiary)] p-2 text-xs",
        className
      )}
    >
      <EventIcon type={type} />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="flex items-center gap-2">
          <span className="font-medium text-[var(--text-primary)]">{type}</span>
          <span className="text-[var(--text-muted)]">step {stepIndex}</span>
        </span>
        {summary !== undefined && summary !== "" ? (
          <span className="truncate text-[var(--text-secondary)]">{summary}</span>
        ) : null}
      </span>
      <Button
        variant="secondary"
        size="sm"
        type="button"
        onClick={() => {
          onSelect(eventId);
        }}
        loading={isPending}
        aria-label={`Fork from ${type} at step ${String(stepIndex)}`}
        data-testid="fork-from-button"
      >
        Fork from here
      </Button>
    </li>
  );
}

/**
 * NotFoundCard organism — C13 "Run not found" state.
 * Rendered by `CenterPanelContainer` when `useRun` reports a 404.
 */

import { Link } from "react-router-dom";

import { GlassSurface } from "@/components/atoms";
import { cn } from "@/lib/cn";

export interface NotFoundCardProps {
  runId?: string | undefined;
  className?: string | undefined;
}

export function NotFoundCard({ runId, className }: NotFoundCardProps) {
  return (
    <GlassSurface
      role="status"
      data-testid="not-found-card"
      variant="default"
      elevation="md"
      radius="md"
      className={cn(
        "mx-auto mt-10 w-full max-w-2xl p-6 text-center",
        className
      )}
    >
      <h2 className="text-lg font-semibold text-[var(--text-primary)]">
        Run not found
      </h2>
      <p className="mt-2 text-sm text-[var(--text-secondary)]">
        {runId !== undefined && runId !== "" ? (
          <>
            We could not find a run with id{" "}
            <code className="rounded-[var(--radius-sm)] bg-[var(--bg-tertiary)] px-1 py-0.5 text-xs">
              {runId}
            </code>
            .
          </>
        ) : (
          "We could not find that run."
        )}
      </p>
      <p className="mt-4 text-sm">
        <Link
          to="/"
          className="text-[var(--accent)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          Start a new research
        </Link>
      </p>
    </GlassSurface>
  );
}

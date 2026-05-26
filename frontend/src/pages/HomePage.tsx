/**
 * HomePage — Route: /
 * Owns: useUser, useRunHistory (wired in future BRDs).
 * See ui-prototype.md §8.2 (Pages).
 */

import {
  AppShell,
  HistoryPanel,
  CenterPanel,
  TracePanel,
} from "@/components/templates";

function HistoryPlaceholder() {
  return (
    <HistoryPanel
      header={
        <h2 className="text-sm font-medium text-[var(--text-primary)]">
          History
        </h2>
      }
      body={
        <p className="px-2 text-sm text-[var(--text-secondary)]">
          You haven&apos;t started any research yet.
        </p>
      }
    />
  );
}

function CenterPlaceholder() {
  return (
    <CenterPanel
      body={
        <div className="mx-auto max-w-2xl pt-16 text-center">
          <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
            Novum
          </h1>
          <p className="mt-2 text-base text-[var(--text-secondary)]">
            Research agent that earns its conclusions.
          </p>
        </div>
      }
    />
  );
}

function TracePlaceholder() {
  return (
    <TracePanel
      header={
        <h2 className="text-sm font-medium text-[var(--text-primary)]">
          Trace
        </h2>
      }
      body={
        <p className="text-xs text-[var(--text-secondary)]">
          The event log will appear here once research starts.
        </p>
      }
    />
  );
}

export default function HomePage() {
  return (
    <AppShell
      left={<HistoryPlaceholder />}
      center={<CenterPlaceholder />}
      right={<TracePlaceholder />}
    />
  );
}

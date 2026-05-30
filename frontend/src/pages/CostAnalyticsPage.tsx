/**
 * CostAnalyticsPage — Route: /costs
 *
 * Standalone full-width page that aggregates cost across ALL runs of the
 * authenticated user. Filters live in local state and drive a single
 * TanStack Query (useCostAnalytics).
 *
 * Per `eslint.config.js`, data-fetching hooks may only be imported from
 * `pages/` — this page is the only consumer of `useCostAnalytics`.
 */

import { useCallback, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { ArrowLeft, AlertCircle } from "lucide-react";

import {
  BackgroundOrbs,
  Logo,
  Spinner,
} from "@/components/atoms";
import {
  AnalyticsFilters,
  ThemeToggle,
} from "@/components/molecules";
import {
  CostAnalyticsTable,
  CostDashboard,
} from "@/components/organisms";
import { useCostAnalytics } from "@/hooks/useCostAnalytics";
import { useUserStore } from "@/stores/userStore";
import type { CostAnalyticsFilters } from "@/types/costAnalytics";

export default function CostAnalyticsPage() {
  const [filters, setFilters] = useState<CostAnalyticsFilters>({});
  const isAuthenticated = useUserStore((s) => s.isAuthenticated);
  const isVerifying = useUserStore((s) => s.isVerifying);

  const { data, isLoading, isError, error, refetch, isRefetching } =
    useCostAnalytics(filters);

  const onReset = useCallback((): void => {
    setFilters({});
  }, []);
  const onRefresh = useCallback((): void => {
    void refetch();
  }, [refetch]);

  if (isVerifying) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }
  if (!isAuthenticated) {
    return <Navigate to="/run" replace />;
  }

  return (
    <div className="relative min-h-dvh w-full overflow-x-hidden text-(--text-primary)">
      <BackgroundOrbs />
      <TopNav />

      <main className="relative z-10 mx-auto w-full max-w-7xl px-6 pt-8 pb-24 sm:px-8">
        <header className="mb-6 flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            Cost analytics
          </h1>
          <p className="text-sm text-(--text-secondary)">
            Aggregate spend across all runs (global view). Filter by user to drill down.
          </p>
        </header>

        <AnalyticsFilters
          filters={filters}
          onChange={setFilters}
          onReset={onReset}
          onRefresh={onRefresh}
          isRefreshing={isRefetching}
          owners={data?.by_user.map((u) => u.owner) ?? []}
          className="mb-6"
        />

        {isLoading ? (
          <div className="flex items-center justify-center py-24" data-testid="analytics-loading">
            <Spinner size="lg" />
          </div>
        ) : isError ? (
          <div
            role="alert"
            data-testid="analytics-error"
            className="flex flex-col items-center gap-3 rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-(--glass-bg) p-12 text-center"
          >
            <AlertCircle className="h-6 w-6 text-(--text-secondary)" />
            <p className="text-sm text-(--text-primary)">
              Could not load cost analytics.
            </p>
            <p className="text-xs text-(--text-secondary)">
              {error instanceof Error ? error.message : "Unknown error"}
            </p>
            <button
              type="button"
              onClick={onRefresh}
              className="rounded-md border border-[var(--glass-border)] px-3 py-1.5 text-xs hover:bg-(--glass-hover)"
            >
              Try again
            </button>
          </div>
        ) : data !== undefined ? (
          <div className="flex flex-col gap-6">
            <CostDashboard data={data} />
            <CostAnalyticsTable rows={data.rows} />
          </div>
        ) : null}
      </main>
    </div>
  );
}

function TopNav() {
  return (
    <header className="relative z-20 border-b border-(--glass-border) bg-(--bg-secondary)/60 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6 sm:px-8">
        <Link
          to="/run"
          className="inline-flex items-center gap-2 text-sm font-medium text-(--text-primary) transition-opacity hover:opacity-80"
        >
          <Logo size={20} title="" />
          <span>Novum</span>
        </Link>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Link
            to="/run"
            className="group inline-flex items-center gap-2 rounded-lg border border-(--glass-border) bg-(--glass-bg) px-3 py-1.5 text-xs text-(--text-secondary) transition-colors hover:bg-(--glass-hover) hover:text-(--text-primary)"
          >
            <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
            Back to Novum
          </Link>
        </div>
      </div>
    </header>
  );
}

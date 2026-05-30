/**
 * CostDashboard organism — composes KPI cards and the four analytics charts.
 */

import { Activity, Coins, Cpu, Database } from "lucide-react";

import { KpiCard } from "@/components/atoms";
import {
  CostDonut,
  CostLineChart,
  KindBarChart,
  TopModelsChart,
  UserBarChart,
} from "@/components/molecules";
import {
  formatInt,
  formatTokens,
  formatUsd,
} from "@/lib/costAnalyticsFormat";
import type { CostAnalyticsResponse } from "@/types/costAnalytics";

export interface CostDashboardProps {
  data: CostAnalyticsResponse;
}

export function CostDashboard({ data }: CostDashboardProps) {
  const totalTokens = data.totals.prompt_tokens + data.totals.completion_tokens;

  return (
    <div className="flex flex-col gap-4" data-testid="cost-dashboard">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Total cost"
          value={formatUsd(data.totals.cost_usd)}
          sub={`${formatInt(data.totals.calls)} calls`}
          icon={<Coins className="h-4 w-4" />}
          testId="kpi-total-cost"
        />
        <KpiCard
          label="Total tokens"
          value={formatTokens(totalTokens)}
          sub={`${formatInt(data.totals.prompt_tokens)} in · ${formatInt(data.totals.completion_tokens)} out`}
          icon={<Cpu className="h-4 w-4" />}
          testId="kpi-total-tokens"
        />
        <KpiCard
          label="Runs"
          value={formatInt(data.totals.runs)}
          sub={`${data.date_from} → ${data.date_to}`}
          icon={<Database className="h-4 w-4" />}
          testId="kpi-runs"
        />
        <KpiCard
          label="Avg / run"
          value={
            data.totals.runs > 0
              ? formatUsd(data.totals.cost_usd / data.totals.runs)
              : formatUsd(0)
          }
          sub={
            data.totals.runs > 0
              ? `${formatInt(Math.round(data.totals.calls / data.totals.runs))} calls / run`
              : "—"
          }
          icon={<Activity className="h-4 w-4" />}
          testId="kpi-avg-per-run"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CostLineChart data={data.by_day} />
        <CostDonut data={data.by_provider} />
        <KindBarChart data={data.by_kind} />
        <UserBarChart data={data.by_user} />
        <TopModelsChart data={data.by_model} />
      </div>
    </div>
  );
}

/**
 * CostLineChart — daily $ and tokens trend.
 */

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DailyPoint } from "@/types/costAnalytics";
import {
  CHART_COLORS,
  formatShortDate,
  formatTokens,
  formatUsd,
} from "@/lib/costAnalyticsFormat";
import { ChartFrame } from "./ChartFrame";

export interface CostLineChartProps {
  data: DailyPoint[];
  height?: number;
}

export function CostLineChart({ data, height = 280 }: CostLineChartProps) {
  return (
    <ChartFrame title="Daily cost & tokens" testId="cost-line-chart">
      {data.length === 0 ? (
        <EmptyState />
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              tickFormatter={formatShortDate}
              tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
              stroke="var(--glass-border)"
            />
            <YAxis
              yAxisId="usd"
              tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
              stroke="var(--glass-border)"
              tickFormatter={(v: number) => formatUsd(v)}
              width={70}
            />
            <YAxis
              yAxisId="tok"
              orientation="right"
              tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
              stroke="var(--glass-border)"
              tickFormatter={(v: number) => formatTokens(v)}
            />
            <Tooltip
              contentStyle={{
                background: "var(--glass-bg)",
                border: "1px solid var(--glass-border)",
                borderRadius: 8,
                color: "var(--text-primary)",
                fontSize: 12,
              }}
              labelFormatter={(label: string) => formatShortDate(label)}
              formatter={(value: number, name: string) =>
                name === "cost_usd"
                  ? [formatUsd(value), "Cost"]
                  : [formatTokens(value), "Tokens"]
              }
            />
            <Line
              yAxisId="usd"
              type="monotone"
              dataKey="cost_usd"
              stroke={CHART_COLORS[0]}
              strokeWidth={2}
              dot={false}
              name="cost_usd"
            />
            <Line
              yAxisId="tok"
              type="monotone"
              dataKey="tokens"
              stroke={CHART_COLORS[2]}
              strokeWidth={2}
              dot={false}
              name="tokens"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </ChartFrame>
  );
}

function EmptyState() {
  return (
    <p className="py-12 text-center text-sm text-(--text-secondary)">
      No data in the selected range.
    </p>
  );
}

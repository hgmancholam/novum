/**
 * UserBarChart — cost by user/owner (global dashboard breakdown).
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { UserBreakdown } from "@/types/costAnalytics";
import { CHART_COLORS, formatUsd } from "@/lib/costAnalyticsFormat";
import { ChartFrame } from "./ChartFrame";

export interface UserBarChartProps {
  data: UserBreakdown[];
  height?: number;
}

export function UserBarChart({ data, height = 280 }: UserBarChartProps) {
  return (
    <ChartFrame title="Cost by user" testId="user-bar-chart">
      {data.length === 0 ? (
        <p className="py-12 text-center text-sm text-(--text-secondary)">
          No cost yet.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <XAxis
              dataKey="owner"
              tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
              stroke="var(--glass-border)"
              interval={0}
              angle={-20}
              textAnchor="end"
              height={50}
            />
            <YAxis
              tickFormatter={(v: number) => formatUsd(v)}
              tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
              stroke="var(--glass-border)"
              width={70}
            />
            <Tooltip
              contentStyle={{
                background: "var(--glass-bg)",
                border: "1px solid var(--glass-border)",
                borderRadius: 8,
                color: "var(--text-primary)",
                fontSize: 12,
              }}
              formatter={(value) => [formatUsd(Number(value ?? 0)), "Cost"]}
            />
            <Bar dataKey="cost_usd" radius={[6, 6, 0, 0]}>
              {data.map((row, i) => (
                <Cell
                  key={row.owner}
                  fill={CHART_COLORS[i % CHART_COLORS.length] ?? "#64748b"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartFrame>
  );
}

/**
 * KindBarChart — cost by call kind (llm / search / fetch).
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

import type { KindBreakdown } from "@/types/costAnalytics";
import { colorForKind, formatUsd } from "@/lib/costAnalyticsFormat";
import { ChartFrame } from "./ChartFrame";

export interface KindBarChartProps {
  data: KindBreakdown[];
  height?: number;
}

export function KindBarChart({ data, height = 280 }: KindBarChartProps) {
  return (
    <ChartFrame title="Cost by kind" testId="kind-bar-chart">
      {data.length === 0 ? (
        <p className="py-12 text-center text-sm text-(--text-secondary)">
          No cost yet.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <XAxis
              dataKey="kind"
              tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
              stroke="var(--glass-border)"
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
              formatter={(value: number) => [formatUsd(value), "Cost"]}
            />
            <Bar dataKey="cost_usd" radius={[6, 6, 0, 0]}>
              {data.map((row) => (
                <Cell key={row.kind} fill={colorForKind(row.kind)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartFrame>
  );
}

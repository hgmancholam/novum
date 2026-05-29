/**
 * TopModelsChart — horizontal bar chart of top-N models by cost.
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

import type { ModelBreakdown } from "@/types/costAnalytics";
import { colorForProvider, formatUsd } from "@/lib/costAnalyticsFormat";
import { ChartFrame } from "./ChartFrame";

export interface TopModelsChartProps {
  data: ModelBreakdown[];
  height?: number;
}

export function TopModelsChart({ data, height = 320 }: TopModelsChartProps) {
  return (
    <ChartFrame title="Top models by cost" testId="top-models-chart">
      {data.length === 0 ? (
        <p className="py-12 text-center text-sm text-(--text-secondary)">
          No model data yet.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart
            layout="vertical"
            data={data}
            margin={{ top: 8, right: 16, left: 24, bottom: 0 }}
          >
            <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <XAxis
              type="number"
              tickFormatter={(v: number) => formatUsd(v)}
              tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
              stroke="var(--glass-border)"
            />
            <YAxis
              type="category"
              dataKey="model"
              tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
              stroke="var(--glass-border)"
              width={150}
            />
            <Tooltip
              contentStyle={{
                background: "var(--glass-bg)",
                border: "1px solid var(--glass-border)",
                borderRadius: 8,
                color: "var(--text-primary)",
                fontSize: 12,
              }}
              formatter={(value, _name, item) => {
                const n = Number(value ?? 0);
                const row = (item as { payload?: ModelBreakdown } | undefined)
                  ?.payload;
                return [
                  formatUsd(n),
                  `${row?.provider ?? ""} · ${row?.model ?? ""}`,
                ];
              }}
            />
            <Bar dataKey="cost_usd" radius={[0, 6, 6, 0]}>
              {data.map((row) => (
                <Cell
                  key={`${row.provider}-${row.model}`}
                  fill={colorForProvider(row.provider)}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartFrame>
  );
}

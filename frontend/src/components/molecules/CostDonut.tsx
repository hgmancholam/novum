/**
 * CostDonut — provider share of total cost.
 */

import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import type { ProviderBreakdown } from "@/types/costAnalytics";
import { colorForProvider, formatUsd } from "@/lib/costAnalyticsFormat";
import { ChartFrame } from "./ChartFrame";

export interface CostDonutProps {
  data: ProviderBreakdown[];
  height?: number;
}

export function CostDonut({ data, height = 280 }: CostDonutProps) {
  const total = data.reduce((acc, r) => acc + r.cost_usd, 0);

  return (
    <ChartFrame title="Cost by provider" testId="cost-donut">
      {data.length === 0 || total === 0 ? (
        <p className="py-12 text-center text-sm text-(--text-secondary)">
          No cost yet.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <PieChart>
            <Pie
              data={data}
              dataKey="cost_usd"
              nameKey="provider"
              innerRadius="55%"
              outerRadius="80%"
              paddingAngle={2}
              stroke="var(--bg-primary)"
            >
              {data.map((row) => (
                <Cell key={row.provider} fill={colorForProvider(row.provider)} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "var(--glass-bg)",
                border: "1px solid var(--glass-border)",
                borderRadius: 8,
                color: "var(--text-primary)",
                fontSize: 12,
              }}
              formatter={(value: number, _name: string, payload) => {
                const row = payload?.payload as ProviderBreakdown | undefined;
                return [
                  `${formatUsd(value)} (${row?.pct_of_total.toFixed(1) ?? "0"}%)`,
                  row?.provider ?? "",
                ];
              }}
            />
            <Legend
              wrapperStyle={{
                color: "var(--text-secondary)",
                fontSize: 12,
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      )}
    </ChartFrame>
  );
}

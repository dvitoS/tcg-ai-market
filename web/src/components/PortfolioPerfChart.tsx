"use client";

import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useLocale } from "@/components/LocaleProvider";
import { formatMoney } from "@/lib/api";
import type { PortfolioPerfPoint } from "@/lib/types";

function shortDate(value: string): string {
  const d = new Date(`${value}T00:00:00Z`);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function PortfolioPerfChart({
  points,
}: {
  points: PortfolioPerfPoint[];
}) {
  const { t } = useLocale();
  const rows = useMemo(
    () =>
      points.map((p) => ({
        date: p.date,
        label: shortDate(p.date),
        invested: Number(p.invested || 0),
        market_value: Number(p.market_value || 0),
      })),
    [points],
  );

  if (rows.length < 2) {
    return null;
  }

  return (
    <div className="chart-panel portfolio-perf">
      <div className="chart-head">
        <h2>{t("port_perf_title")}</h2>
        <p>{t("port_perf_lede")}</p>
      </div>
      <div className="chart-frame">
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
            <defs>
              <linearGradient id="portValueFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#b87333" stopOpacity={0.28} />
                <stop offset="100%" stopColor="#b87333" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "#a1a1aa", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              minTickGap={28}
            />
            <YAxis
              tick={{ fill: "#a1a1aa", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={56}
              tickFormatter={(v) => formatMoney(Number(v))}
            />
            <Tooltip
              cursor={{ stroke: "rgba(255,255,255,0.12)" }}
              contentStyle={{
                background: "#1a1a1a",
                border: "1px solid #2a2a2a",
                borderRadius: 10,
              }}
              labelFormatter={(_, payload) => {
                const row = payload?.[0]?.payload as { date?: string } | undefined;
                return row?.date || "";
              }}
              formatter={(value) => formatMoney(Number(value ?? 0))}
            />
            <Legend />
            <Area
              type="monotone"
              dataKey="market_value"
              name={t("kpi_value")}
              stroke="#b87333"
              strokeWidth={2.25}
              fill="url(#portValueFill)"
              dot={false}
              activeDot={{ r: 3 }}
            />
            <Line
              type="monotone"
              dataKey="invested"
              name={t("kpi_invested")}
              stroke="#64748b"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 3 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

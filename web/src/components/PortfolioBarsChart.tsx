"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatMoney } from "@/lib/api";
import type { PortfolioLot } from "@/lib/types";

function shortName(value: string | null | undefined, fallback: string): string {
  const raw = (value || fallback).trim();
  return raw.length > 18 ? `${raw.slice(0, 16)}…` : raw;
}

export function PortfolioBarsChart({ lots }: { lots: PortfolioLot[] }) {
  const rows = useMemo(
    () =>
      lots
        .filter((lot) => String(lot.status || "open").toLowerCase() !== "sold")
        .map((lot) => ({
          name: shortName(lot.name, lot.card_id),
          invested: Number(lot.invested || 0),
          value: Number(lot.market_value || 0),
        }))
        .filter((row) => row.invested > 0 || row.value > 0)
        .slice(0, 12),
    [lots],
  );

  if (rows.length === 0) {
    return null;
  }

  return (
    <div className="chart-panel portfolio-bars">
      <div className="chart-head">
        <h2>Open lots</h2>
        <p>Cost basis vs mark-to-market value.</p>
      </div>
      <div className="chart-frame">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="name"
              tick={{ fill: "#a1a1aa", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              interval={0}
              angle={rows.length > 6 ? -25 : 0}
              textAnchor={rows.length > 6 ? "end" : "middle"}
              height={rows.length > 6 ? 56 : 28}
            />
            <YAxis
              tick={{ fill: "#a1a1aa", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={56}
              tickFormatter={(v) => formatMoney(Number(v))}
            />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
              contentStyle={{
                background: "#1a1a1a",
                border: "1px solid #2a2a2a",
                borderRadius: 10,
              }}
              formatter={(value) => formatMoney(Number(value ?? 0))}
            />
            <Legend />
            <Bar dataKey="invested" name="Invested" fill="#64748b" radius={[4, 4, 0, 0]} />
            <Bar dataKey="value" name="Value" fill="#b87333" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatMoney } from "@/lib/api";
import type { HistoryPoint } from "@/lib/types";

type RangeKey = "1m" | "3m" | "all";

const RANGES: { key: RangeKey; label: string; days: number | null }[] = [
  { key: "1m", label: "1M", days: 30 },
  { key: "3m", label: "3M", days: 90 },
  { key: "all", label: "All", days: null },
];

function clipPoints(points: HistoryPoint[], range: RangeKey): HistoryPoint[] {
  const cfg = RANGES.find((r) => r.key === range);
  if (!cfg?.days || points.length === 0) return points;
  const last = new Date(`${points[points.length - 1].date}T00:00:00Z`).getTime();
  const cutoff = last - cfg.days * 24 * 60 * 60 * 1000;
  return points.filter((p) => new Date(`${p.date}T00:00:00Z`).getTime() >= cutoff);
}

function shortDate(value: string): string {
  const d = new Date(`${value}T00:00:00Z`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

export function PriceChart({
  points,
  predictedPrice,
}: {
  points: HistoryPoint[];
  predictedPrice?: number | null;
}) {
  const [range, setRange] = useState<RangeKey>("1m");
  const clipped = useMemo(() => clipPoints(points, range), [points, range]);

  const chartData = useMemo(() => {
    const rows = clipped.map((p) => ({
      date: p.date,
      label: shortDate(p.date),
      price: p.price,
    }));
    if (
      predictedPrice != null &&
      !Number.isNaN(predictedPrice) &&
      rows.length > 0
    ) {
      const last = rows[rows.length - 1];
      const next = new Date(`${last.date}T00:00:00Z`);
      next.setUTCDate(next.getUTCDate() + 1);
      const iso = next.toISOString().slice(0, 10);
      rows.push({
        date: iso,
        label: shortDate(iso),
        price: predictedPrice,
      });
    }
    return rows;
  }, [clipped, predictedPrice]);

  if (!points.length) {
    return (
      <div className="chart-panel">
        <div className="chart-head">
          <h2>Price history</h2>
          <p>No history points for this card yet.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chart-panel">
      <div className="chart-head">
        <div>
          <h2>Price history</h2>
          <p>Market series · Soft Ink chart</p>
        </div>
        <div className="range-toggle" role="tablist" aria-label="Chart range">
          {RANGES.map((item) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={range === item.key}
              className={range === item.key ? "is-active" : ""}
              onClick={() => setRange(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className="chart-canvas">
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={chartData} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#B87333" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#B87333" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(42,42,42,0.9)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "#a1a1aa", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              minTickGap={28}
            />
            <YAxis
              tick={{ fill: "#a1a1aa", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={56}
              tickFormatter={(v) => `$${Number(v).toFixed(2)}`}
              domain={["auto", "auto"]}
            />
            <Tooltip
              contentStyle={{
                background: "#1a1a1a",
                border: "1px solid #2a2a2a",
                borderRadius: 10,
                color: "#f4f4f5",
              }}
              labelStyle={{ color: "#a1a1aa" }}
              formatter={(value) => [formatMoney(Number(value), "USD", 4), "Price"]}
            />
            <Area
              type="monotone"
              dataKey="price"
              stroke="#B87333"
              strokeWidth={2.2}
              fill="url(#priceFill)"
              dot={false}
              activeDot={{ r: 4, fill: "#D4A574", stroke: "#121212", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

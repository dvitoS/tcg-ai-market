"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useLocale } from "@/components/LocaleProvider";
import { fetchCardPriceSources, formatMoney } from "@/lib/api";
import type { HistoryPoint } from "@/lib/types";

type RangeKey = "1m" | "3m" | "all";

const RANGES: { key: RangeKey; label: string; days: number | null }[] = [
  { key: "1m", label: "1M", days: 30 },
  { key: "3m", label: "3M", days: 90 },
  { key: "all", label: "All", days: null },
];

const PSA_COLOR = "#c9a227";

function clipPoints(points: HistoryPoint[], range: RangeKey): HistoryPoint[] {
  const cfg = RANGES.find((r) => r.key === range);
  if (!cfg?.days || points.length === 0) return points;
  const last = new Date(
    `${points[points.length - 1].date}T00:00:00Z`,
  ).getTime();
  const cutoff = last - cfg.days * 24 * 60 * 60 * 1000;
  return points.filter(
    (p) => new Date(`${p.date}T00:00:00Z`).getTime() >= cutoff,
  );
}

function shortDate(value: string, locale: string): string {
  const d = new Date(`${value}T00:00:00Z`);
  return d.toLocaleDateString(locale === "hr" ? "hr-HR" : "en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function GradedPriceChart({ cardId }: { cardId: string }) {
  const { t, locale } = useLocale();
  const [armed, setArmed] = useState(false);
  const [range, setRange] = useState<RangeKey>("3m");
  const [points, setPoints] = useState<HistoryPoint[]>([]);
  const [salesCount, setSalesCount] = useState<number | null>(null);
  const [periodKey, setPeriodKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setArmed(false);
    setPoints([]);
    setSalesCount(null);
    setPeriodKey(null);
    setError(null);
    setLoading(false);
  }, [cardId]);

  useEffect(() => {
    if (!armed) return;
    let alive = true;
    setLoading(true);
    setError(null);
    void fetchCardPriceSources(cardId, { grades: "psa10" })
      .then((payload) => {
        if (!alive) return;
        if (payload.psa10_error) {
          setError(payload.psa10_error);
        }
        setPoints(payload.psa10 || []);
        const sales = payload.psa10_stats?.sales_count;
        setSalesCount(
          sales != null && Number.isFinite(Number(sales))
            ? Number(sales)
            : null,
        );
        setPeriodKey(payload.psa10_stats?.period_key || null);
      })
      .catch((err) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : t("chart_graded_error"));
        setPoints([]);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [armed, cardId, t]);

  const clipped = useMemo(() => clipPoints(points, range), [points, range]);
  const chartData = useMemo(
    () =>
      clipped.map((p) => ({
        date: p.date,
        label: shortDate(p.date, locale),
        psa10: Number(p.price),
      })),
    [clipped, locale],
  );

  return (
    <div className="chart-panel chart-panel-graded" aria-label={t("chart_graded_title")}>
      <div className="chart-head">
        <div>
          <h2>{t("chart_graded_title")}</h2>
          <p>{t("chart_graded_subtitle")}</p>
        </div>
        {armed ? (
          <div className="range-toggle" role="tablist" aria-label="Graded chart range">
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
        ) : null}
      </div>

      {!armed ? (
        <p className="grade-ev-idle">
          <button
            type="button"
            className="btn-primary"
            onClick={() => setArmed(true)}
          >
            {t("chart_graded_load")}
          </button>
          <span className="lot-meta">{t("chart_graded_load_hint")}</span>
        </p>
      ) : null}

      {armed && loading ? (
        <p className="chart-sources-status">{t("chart_graded_loading")}</p>
      ) : null}
      {armed && error && chartData.length === 0 ? (
        <p className="form-error">
          {/rate.?limit/i.test(error)
            ? t("chart_psa_rate_limited")
            : error}
        </p>
      ) : null}
      {armed && !loading && !error && chartData.length === 0 ? (
        <p className="chart-sources-status">{t("chart_psa_empty")}</p>
      ) : null}

      {armed && chartData.length > 0 ? (
        <>
          <p className="chart-sources-status">
            {t("chart_graded_depth", {
              count: String(clipped.length),
              sales:
                salesCount != null ? String(Math.round(salesCount)) : "—",
              window: periodKey || "—",
            })}
          </p>
          <div className="chart-canvas">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart
                data={chartData}
                margin={{ top: 12, right: 8, left: 0, bottom: 0 }}
              >
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
                  tickFormatter={(v) => `$${Number(v).toFixed(0)}`}
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
                  formatter={(value) => [
                    typeof value === "number"
                      ? formatMoney(value, "USD", 2)
                      : "—",
                    t("chart_series_psa"),
                  ]}
                />
                <Line
                  type="monotone"
                  dataKey="psa10"
                  name={t("chart_series_psa")}
                  stroke={PSA_COLOR}
                  strokeWidth={2.2}
                  dot={false}
                  connectNulls
                  activeDot={{
                    r: 4,
                    fill: "#e0c56a",
                    stroke: "#121212",
                    strokeWidth: 2,
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : null}
    </div>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
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

type RangeKey = "1m" | "3m" | "1y" | "all";
type GradeKey = "psa10" | "psa9";

/** Soft Ink board is USD — auto-load graded when NM spot ≥ this. */
export const GRADED_AUTO_MIN_USD = 50;

const RANGES: { key: RangeKey; label: string; days: number | null }[] = [
  { key: "1m", label: "1M", days: 30 },
  { key: "3m", label: "3M", days: 90 },
  { key: "1y", label: "1Y", days: 365 },
  { key: "all", label: "All", days: null },
];

const GRADE_META: Record<GradeKey, { color: string; dash?: string }> = {
  psa10: { color: "#c9a227" },
  psa9: { color: "#8b9dc3", dash: "5 4" },
};

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

function mergeGradeSeries(
  psa10: HistoryPoint[],
  psa9: HistoryPoint[],
  locale: string,
): Array<Record<string, string | number | null>> {
  const byDate = new Map<string, Record<string, string | number | null>>();
  for (const p of psa10) {
    byDate.set(p.date, {
      date: p.date,
      label: shortDate(p.date, locale),
      psa10: Number(p.price),
      psa9: null,
    });
  }
  for (const p of psa9) {
    const row = byDate.get(p.date) || {
      date: p.date,
      label: shortDate(p.date, locale),
      psa10: null,
      psa9: null,
    };
    row.psa9 = Number(p.price);
    byDate.set(p.date, row);
  }
  return Array.from(byDate.values()).sort((a, b) =>
    String(a.date).localeCompare(String(b.date)),
  );
}

export function GradedPriceChart({
  cardId,
  nmSpotUsd,
}: {
  cardId: string;
  /** Board / history NM tip (USD). ≥ $50 auto-loads PSA 9 + 10. */
  nmSpotUsd?: number | null;
}) {
  const { t, locale } = useLocale();
  const autoArm =
    nmSpotUsd != null &&
    Number.isFinite(Number(nmSpotUsd)) &&
    Number(nmSpotUsd) >= GRADED_AUTO_MIN_USD;

  const [armed, setArmed] = useState(autoArm);
  const [range, setRange] = useState<RangeKey>("3m");
  const [psa10, setPsa10] = useState<HistoryPoint[]>([]);
  const [psa9, setPsa9] = useState<HistoryPoint[]>([]);
  const [sales10, setSales10] = useState<number | null>(null);
  const [sales9, setSales9] = useState<number | null>(null);
  const [periodKey, setPeriodKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visible, setVisible] = useState<Record<GradeKey, boolean>>({
    psa10: true,
    psa9: true,
  });

  useEffect(() => {
    setArmed(autoArm);
    setPsa10([]);
    setPsa9([]);
    setSales10(null);
    setSales9(null);
    setPeriodKey(null);
    setError(null);
    setLoading(false);
    setVisible({ psa10: true, psa9: true });
  }, [cardId, autoArm]);

  useEffect(() => {
    if (!armed) return;
    let alive = true;
    setLoading(true);
    setError(null);
    // PSA 9 + 10 — "all graded" comps for Soft Ink detail.
    void fetchCardPriceSources(cardId, { grades: "all" })
      .then((payload) => {
        if (!alive) return;
        const err = payload.psa10_error || payload.psa9_error;
        if (err && !(payload.psa10?.length || payload.psa9?.length)) {
          setError(err);
        } else if (payload.psa10_error && !payload.psa10?.length) {
          setError(payload.psa10_error);
        }
        setPsa10(payload.psa10 || []);
        setPsa9(payload.psa9 || []);
        const s10 = payload.psa10_stats?.sales_count;
        const s9 = payload.psa9_stats?.sales_count;
        setSales10(
          s10 != null && Number.isFinite(Number(s10)) ? Number(s10) : null,
        );
        setSales9(
          s9 != null && Number.isFinite(Number(s9)) ? Number(s9) : null,
        );
        setPeriodKey(
          payload.psa10_stats?.period_key ||
            payload.psa9_stats?.period_key ||
            null,
        );
      })
      .catch((err) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : t("chart_graded_error"));
        setPsa10([]);
        setPsa9([]);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [armed, cardId, t]);

  const psa10Clip = useMemo(() => clipPoints(psa10, range), [psa10, range]);
  const psa9Clip = useMemo(() => clipPoints(psa9, range), [psa9, range]);
  const chartData = useMemo(
    () => mergeGradeSeries(psa10Clip, psa9Clip, locale),
    [psa10Clip, psa9Clip, locale],
  );
  const hasSeries = chartData.length > 0;

  const gradeLabels: Record<GradeKey, string> = {
    psa10: t("chart_series_psa"),
    psa9: t("chart_series_psa9"),
  };

  return (
    <div
      className="chart-panel chart-panel-graded"
      aria-label={t("chart_graded_title")}
    >
      <div className="chart-head">
        <div>
          <h2>{t("chart_graded_title")}</h2>
          <p>
            {autoArm
              ? t("chart_graded_subtitle_auto", {
                  min: String(GRADED_AUTO_MIN_USD),
                })
              : t("chart_graded_subtitle")}
          </p>
        </div>
        {armed ? (
          <div
            className="range-toggle"
            role="tablist"
            aria-label="Graded chart range"
          >
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
      {armed && error && !hasSeries ? (
        <p className="form-error">
          {/rate.?limit/i.test(error) ? t("chart_psa_rate_limited") : error}
        </p>
      ) : null}
      {armed && !loading && !error && !hasSeries ? (
        <p className="chart-sources-status">{t("chart_psa_empty")}</p>
      ) : null}

      {armed && hasSeries ? (
        <>
          <div
            className="chart-series-toggles"
            role="group"
            aria-label="Graded series"
          >
            {(Object.keys(GRADE_META) as GradeKey[]).map((key) => {
              const meta = GRADE_META[key];
              const count = key === "psa10" ? psa10Clip.length : psa9Clip.length;
              const disabled = count === 0;
              return (
                <button
                  key={key}
                  type="button"
                  className={`chart-series-toggle${visible[key] ? " is-on" : ""}${disabled ? " is-disabled" : ""}`}
                  style={{ ["--series-color" as string]: meta.color }}
                  onClick={() =>
                    !disabled &&
                    setVisible((prev) => ({ ...prev, [key]: !prev[key] }))
                  }
                  disabled={disabled}
                  aria-pressed={visible[key]}
                >
                  <span className="chart-series-swatch" aria-hidden />
                  {gradeLabels[key]}
                  <span className="chart-series-count">{count}</span>
                </button>
              );
            })}
          </div>
          <p className="chart-sources-status">
            {t("chart_graded_depth_both", {
              s10: sales10 != null ? String(Math.round(sales10)) : "—",
              s9: sales9 != null ? String(Math.round(sales9)) : "—",
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
                  formatter={(value, name) => [
                    typeof value === "number"
                      ? formatMoney(value, "USD", 2)
                      : "—",
                    String(name),
                  ]}
                />
                <Legend />
                {visible.psa10 && psa10Clip.length > 0 ? (
                  <Line
                    type="monotone"
                    dataKey="psa10"
                    name={gradeLabels.psa10}
                    stroke={GRADE_META.psa10.color}
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
                ) : null}
                {visible.psa9 && psa9Clip.length > 0 ? (
                  <Line
                    type="monotone"
                    dataKey="psa9"
                    name={gradeLabels.psa9}
                    stroke={GRADE_META.psa9.color}
                    strokeWidth={2}
                    strokeDasharray={GRADE_META.psa9.dash}
                    dot={false}
                    connectNulls
                  />
                ) : null}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : null}
    </div>
  );
}

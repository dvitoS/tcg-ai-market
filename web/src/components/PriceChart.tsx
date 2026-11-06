"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useLocale } from "@/components/LocaleProvider";
import { fetchCardPriceSources, formatMoney } from "@/lib/api";
import type { CardPriceSourcesResponse, HistoryPoint } from "@/lib/types";

type RangeKey = "1m" | "3m" | "all";
type SeriesKey = "tcgplayer" | "justtcg" | "psa10";

const RANGES: { key: RangeKey; label: string; days: number | null }[] = [
  { key: "1m", label: "1M", days: 30 },
  { key: "3m", label: "3M", days: 90 },
  { key: "all", label: "All", days: null },
];

const SERIES_META: Record<
  SeriesKey,
  { color: string; strokeDasharray?: string }
> = {
  tcgplayer: { color: "#B87333" },
  justtcg: { color: "#5a9e9e" },
  psa10: {
    color: "#c9a227",
    strokeDasharray: "6 4",
  },
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

function shortDate(value: string): string {
  const d = new Date(`${value}T00:00:00Z`);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function mergeSeries(
  tcg: HistoryPoint[],
  just: HistoryPoint[],
  psa: HistoryPoint[],
): Array<Record<string, string | number | null>> {
  const byDate = new Map<string, Record<string, string | number | null>>();
  for (const p of tcg) {
    byDate.set(p.date, {
      date: p.date,
      label: shortDate(p.date),
      tcgplayer: Number(p.price),
      justtcg: null,
      psa10: null,
    });
  }
  for (const p of just) {
    const row = byDate.get(p.date) || {
      date: p.date,
      label: shortDate(p.date),
      tcgplayer: null,
      justtcg: null,
      psa10: null,
    };
    row.justtcg = Number(p.price);
    byDate.set(p.date, row);
  }
  for (const p of psa) {
    const row = byDate.get(p.date) || {
      date: p.date,
      label: shortDate(p.date),
      tcgplayer: null,
      justtcg: null,
      psa10: null,
    };
    row.psa10 = Number(p.price);
    byDate.set(p.date, row);
  }
  return Array.from(byDate.values()).sort((a, b) =>
    String(a.date).localeCompare(String(b.date)),
  );
}

export function PriceChart({
  cardId,
  points,
  predictedPrice,
}: {
  cardId?: string;
  points: HistoryPoint[];
  predictedPrice?: number | null;
}) {
  const { t } = useLocale();
  const [range, setRange] = useState<RangeKey>("1m");
  const [sources, setSources] = useState<CardPriceSourcesResponse | null>(null);
  // SSR points paint immediately; JustTCG/PSA enhance in the background.
  const [loading, setLoading] = useState(Boolean(cardId) && points.length === 0);
  const [error, setError] = useState<string | null>(null);
  const [visible, setVisible] = useState<Record<SeriesKey, boolean>>({
    tcgplayer: true,
    justtcg: true,
    psa10: true,
  });
  const seriesLabels: Record<SeriesKey, string> = {
    tcgplayer: t("chart_series_tcg"),
    justtcg: t("chart_series_just"),
    psa10: t("chart_series_psa"),
  };

  useEffect(() => {
    if (!cardId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    // Keep chart interactive on SSR history; only show loading if we have nothing yet.
    // NM/DB first — skip graded JustTCG so browsing many details stays cheap.
    if (points.length === 0) setLoading(true);
    setError(null);
    setSources(null);
    fetchCardPriceSources(cardId, { grades: "none" })
      .then((data) => {
        if (!cancelled) setSources(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Sources failed");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cardId, points.length]);

  // Deferred PSA 10 only when the series is visible (default on) — never PSA 9.
  useEffect(() => {
    if (!cardId || !sources || !visible.psa10) return;
    if (sources.grades === "psa10" || sources.grades === "all") return;
    if ((sources.psa10?.length ?? 0) > 0 || sources.psa10_error) return;
    let cancelled = false;
    fetchCardPriceSources(cardId, { grades: "psa10" })
      .then((graded) => {
        if (cancelled) return;
        setSources((prev) => {
          if (!prev) return graded;
          return {
            ...prev,
            psa10: graded.psa10,
            psa10_error: graded.psa10_error,
            psa10_stats: graded.psa10_stats,
            grades: graded.grades ?? "psa10",
            tcgplayer: prev.tcgplayer?.length
              ? prev.tcgplayer
              : graded.tcgplayer,
            justtcg: prev.justtcg?.length ? prev.justtcg : graded.justtcg,
            justtcg_fallback: prev.justtcg_fallback || graded.justtcg_fallback,
            justtcg_from_db: prev.justtcg_from_db || graded.justtcg_from_db,
            justtcg_error: prev.justtcg_error ?? graded.justtcg_error,
            tcgplayer_id: prev.tcgplayer_id ?? graded.tcgplayer_id,
          };
        });
      })
      .catch(() => {
        /* soft fail — NM chart still works */
      });
    return () => {
      cancelled = true;
    };
  }, [cardId, sources, visible.psa10]);

  const tcgAll = sources?.tcgplayer?.length ? sources.tcgplayer : points;
  const justAll = sources?.justtcg || [];
  const psaAll = sources?.psa10 || [];

  const tcgPoints = useMemo(
    () => clipPoints(tcgAll, range),
    [tcgAll, range],
  );
  const justPoints = useMemo(
    () => clipPoints(justAll, range),
    [justAll, range],
  );
  const psaPoints = useMemo(
    () => clipPoints(psaAll, range),
    [psaAll, range],
  );

  const chartData = useMemo(
    () => mergeSeries(tcgPoints, justPoints, psaPoints),
    [tcgPoints, justPoints, psaPoints],
  );

  if (!points.length && !chartData.length) {
    return (
      <div className="chart-panel">
        <div className="chart-head">
          <h2>{t("chart_title")}</h2>
          <p>{t("chart_empty")}</p>
        </div>
      </div>
    );
  }

  function toggle(key: SeriesKey) {
    setVisible((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  return (
    <div className="chart-panel">
      <div className="chart-head">
        <div>
          <h2>{t("chart_title")}</h2>
          <p>{t("chart_subtitle")}</p>
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

      <div className="chart-series-toggles" role="group" aria-label="Price sources">
        {(Object.keys(SERIES_META) as SeriesKey[]).map((key) => {
          const meta = SERIES_META[key];
          const count =
            key === "tcgplayer"
              ? tcgPoints.length
              : key === "justtcg"
                ? justPoints.length
                : psaPoints.length;
          const disabled = count === 0 && key !== "tcgplayer";
          return (
            <button
              key={key}
              type="button"
              className={`chart-series-toggle${visible[key] ? " is-on" : ""}${disabled ? " is-disabled" : ""}`}
              style={{ ["--series-color" as string]: meta.color }}
              onClick={() => !disabled && toggle(key)}
              disabled={disabled}
              aria-pressed={visible[key]}
            >
              <span className="chart-series-swatch" aria-hidden />
              {seriesLabels[key]}
              <span className="chart-series-count">{count}</span>
            </button>
          );
        })}
      </div>

      {loading ? (
        <p className="chart-sources-status">{t("chart_loading")}</p>
      ) : null}
      {error ? (
        <p className="chart-sources-status">{t("chart_fallback", { error })}</p>
      ) : null}
      {sources && !sources.justtcg_configured ? (
        <p className="chart-sources-status">{t("chart_no_key")}</p>
      ) : null}
      {sources?.justtcg_from_db ? (
        <p className="chart-sources-status">{t("chart_just_from_db")}</p>
      ) : null}
      {sources?.justtcg_fallback ? (
        <p className="chart-sources-status">{t("chart_just_fallback")}</p>
      ) : null}
      {sources?.justtcg_error ? (
        <p className="chart-sources-status">JustTCG: {sources.justtcg_error}</p>
      ) : null}
      {sources?.psa10_error ? (
        <p className="chart-sources-status">PSA 10: {sources.psa10_error}</p>
      ) : null}
      {sources?.psa10_stats?.has_history_series === false &&
      sources.psa10_stats.sales_count != null ? (
        <p className="chart-sources-status">
          PSA 10: {sources.psa10_stats.sales_count} sales (no date series).
        </p>
      ) : null}

      <div className="chart-canvas">
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart
            data={chartData}
            margin={{ top: 12, right: 8, left: 0, bottom: 0 }}
          >
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
              formatter={(value, name) => [
                typeof value === "number"
                  ? formatMoney(value, "USD", 4)
                  : "—",
                String(name),
              ]}
            />
            <Legend />
            {visible.tcgplayer ? (
              <Area
                type="monotone"
                dataKey="tcgplayer"
                name={seriesLabels.tcgplayer}
                stroke={SERIES_META.tcgplayer.color}
                strokeWidth={2.2}
                fill="url(#priceFill)"
                dot={false}
                connectNulls
                activeDot={{
                  r: 4,
                  fill: "#D4A574",
                  stroke: "#121212",
                  strokeWidth: 2,
                }}
              />
            ) : null}
            {visible.justtcg && justPoints.length > 0 ? (
              <Line
                type="monotone"
                dataKey="justtcg"
                name={seriesLabels.justtcg}
                stroke={SERIES_META.justtcg.color}
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            ) : null}
            {visible.psa10 && psaPoints.length > 0 ? (
              <Line
                type="monotone"
                dataKey="psa10"
                name={seriesLabels.psa10}
                stroke={SERIES_META.psa10.color}
                strokeWidth={2}
                strokeDasharray={SERIES_META.psa10.strokeDasharray}
                dot={false}
                connectNulls
              />
            ) : null}
            {predictedPrice != null && Number.isFinite(predictedPrice) ? (
              <ReferenceLine
                y={predictedPrice}
                stroke="#a1a1aa"
                strokeDasharray="4 4"
                label={{
                  value: `Pred ${formatMoney(predictedPrice, "USD", 2)}`,
                  position: "insideTopRight",
                  fill: "#a1a1aa",
                  fontSize: 11,
                }}
              />
            ) : null}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

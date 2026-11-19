"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useLocale } from "@/components/LocaleProvider";
import {
  MarketSourceTabs,
  type MarketSource,
} from "@/components/MarketSourceTabs";
import { fetchCardPriceSources, formatMoney } from "@/lib/api";
import type { CardPriceSourcesResponse, HistoryPoint } from "@/lib/types";

type RangeKey = "1m" | "3m" | "all";

const RANGES: { key: RangeKey; label: string; days: number | null }[] = [
  { key: "1m", label: "1M", days: 30 },
  { key: "3m", label: "3M", days: 90 },
  { key: "all", label: "All", days: null },
];

const CHART_COLOR = "#B87333";

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

function toChartRows(
  points: HistoryPoint[],
  locale: string,
): Array<Record<string, string | number | null>> {
  return points.map((p) => ({
    date: p.date,
    label: shortDate(p.date, locale),
    price: Number(p.price),
  }));
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
  const { t, locale } = useLocale();
  const [range, setRange] = useState<RangeKey>("1m");
  const [market, setMarket] = useState<MarketSource>("tcgplayer");
  const [sources, setSources] = useState<CardPriceSourcesResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(cardId) && points.length === 0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!cardId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
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

  // Prefer live Soft Ink NM, else DB / SSR history (TCGplayer-linked).
  const nmAll = sources?.justtcg?.length
    ? sources.justtcg
    : sources?.tcgplayer?.length
      ? sources.tcgplayer
      : points;

  const clipped = useMemo(() => clipPoints(nmAll, range), [nmAll, range]);
  const chartData = useMemo(
    () => toChartRows(clipped, locale),
    [clipped, locale],
  );

  if (!points.length && !chartData.length && market === "tcgplayer") {
    return (
      <div className="chart-panel">
        <div className="chart-head">
          <h2>{t("chart_title")}</h2>
          <p>{t("chart_empty")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chart-panel">
      <div className="chart-head chart-head-mkt">
        <div>
          <h2>{t("chart_title")}</h2>
          <p>{t("chart_subtitle")}</p>
        </div>
        <div className="chart-head-controls">
          <MarketSourceTabs
            sources={["tcgplayer", "cardmarket"]}
            value={market === "ebay" ? "tcgplayer" : market}
            onChange={setMarket}
            ariaLabel={t("chart_market_tabs")}
          />
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
      </div>

      {loading ? (
        <p className="chart-sources-status">{t("chart_loading")}</p>
      ) : null}
      {error ? (
        <p className="chart-sources-status">{t("chart_fallback", { error })}</p>
      ) : null}
      {sources?.justtcg_from_db && market === "tcgplayer" ? (
        <p className="chart-sources-status">{t("chart_just_from_db")}</p>
      ) : null}

      {market === "cardmarket" ? (
        <div className="chart-market-empty">
          <p className="chart-market-empty-title">{t("chart_cm_empty_title")}</p>
          <p className="chart-market-empty-lede">{t("chart_cm_empty_lede")}</p>
        </div>
      ) : (
        <div className="chart-canvas">
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart
              data={chartData}
              margin={{ top: 12, right: 8, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CHART_COLOR} stopOpacity={0.35} />
                  <stop
                    offset="100%"
                    stopColor={CHART_COLOR}
                    stopOpacity={0.02}
                  />
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
                formatter={(value) => [
                  typeof value === "number"
                    ? formatMoney(value, "USD", 4)
                    : "—",
                  t("chart_series_tcg_short"),
                ]}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="price"
                name={t("chart_series_tcg_short")}
                stroke={CHART_COLOR}
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
      )}
    </div>
  );
}

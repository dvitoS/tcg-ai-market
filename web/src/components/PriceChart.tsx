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

type RangeKey = "1m" | "3m" | "1y" | "all";

const RANGES: { key: RangeKey; label: string; days: number | null }[] = [
  { key: "1m", label: "1M", days: 30 },
  { key: "3m", label: "3M", days: 90 },
  { key: "1y", label: "1Y", days: 365 },
  { key: "all", label: "All", days: null },
];

const CHART_COLOR = "#B87333";
const CM_CHART_COLOR = "#5B7C99";

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
  const [cmTried, setCmTried] = useState(false);
  const [cmLoading, setCmLoading] = useState(false);

  useEffect(() => {
    if (!cardId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    if (points.length === 0) setLoading(true);
    setError(null);
    setSources(null);
    setCmTried(false);
    // ≥365 pts so 1Y toggle has room when DB / Soft Ink history is long enough.
    fetchCardPriceSources(cardId, { grades: "none", limit: 400 })
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

  // Lazy Cardmarket EUR series — only when the CM tab opens (PkmnPrices credits).
  useEffect(() => {
    if (!cardId || market !== "cardmarket" || !sources || cmTried) return;
    let cancelled = false;
    setCmTried(true);
    setCmLoading(true);
    fetchCardPriceSources(cardId, {
      grades: "none",
      limit: 400,
      cardmarket: true,
    })
      .then((data) => {
        if (cancelled) return;
        setSources((prev) =>
          prev
            ? {
                ...prev,
                cardmarket: data.cardmarket ?? [],
                cardmarket_error: data.cardmarket_error ?? null,
                pkmnprices_used: Boolean(
                  prev.pkmnprices_used || data.pkmnprices_used,
                ),
                pkmnprices_configured: Boolean(
                  prev.pkmnprices_configured || data.pkmnprices_configured,
                ),
              }
            : data,
        );
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setSources((prev) =>
          prev
            ? {
                ...prev,
                cardmarket: prev.cardmarket ?? [],
                cardmarket_error:
                  err instanceof Error
                    ? err.message
                    : "Cardmarket history failed",
              }
            : prev,
        );
      })
      .finally(() => {
        if (!cancelled) setCmLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cardId, market, sources, cmTried]);

  // Prefer live Soft Ink NM, else DB / SSR history (TCGplayer-linked).
  const nmAll = sources?.justtcg?.length
    ? sources.justtcg
    : sources?.tcgplayer?.length
      ? sources.tcgplayer
      : points;

  const cmAll = sources?.cardmarket?.length ? sources.cardmarket : [];
  const activeAll = market === "cardmarket" ? cmAll : nmAll;
  const clipped = useMemo(
    () => clipPoints(activeAll, range),
    [activeAll, range],
  );
  const chartData = useMemo(
    () => toChartRows(clipped, locale),
    [clipped, locale],
  );

  const isCm = market === "cardmarket";
  const seriesColor = isCm ? CM_CHART_COLOR : CHART_COLOR;
  const seriesName = isCm
    ? t("chart_series_cm_short")
    : t("chart_series_tcg_short");
  const moneyCur = isCm ? "EUR" : "USD";
  const tickPrefix = isCm ? "€" : "$";

  if (!points.length && !chartData.length && market === "tcgplayer" && !loading) {
    return (
      <div className="chart-panel">
        <div className="chart-head">
          <h2>{t("chart_title")}</h2>
          <p>{t("chart_empty")}</p>
        </div>
      </div>
    );
  }

  const cmEmpty =
    isCm &&
    !cmLoading &&
    !loading &&
    chartData.length === 0 &&
    cmTried;

  return (
    <div className="chart-panel">
      <div className="chart-head chart-head-mkt">
        <div>
          <h2>{t("chart_title")}</h2>
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

      {loading || cmLoading ? (
        <p className="chart-sources-status">
          {cmLoading ? t("chart_cm_loading") : t("chart_loading")}
        </p>
      ) : null}
      {error ? (
        <p className="chart-sources-status">{t("chart_fallback", { error })}</p>
      ) : null}
      {isCm && sources?.cardmarket_error && chartData.length === 0 && !cmLoading ? (
        <p className="chart-sources-status">{sources.cardmarket_error}</p>
      ) : null}

      {cmEmpty && !sources?.cardmarket_error ? (
        <div className="chart-market-empty">
          <p className="chart-market-empty-title">{t("chart_cm_empty_title")}</p>
          <p className="chart-market-empty-lede">{t("chart_cm_empty_lede")}</p>
        </div>
      ) : !cmEmpty && !(isCm && chartData.length === 0 && cmLoading) ? (
        <div className="chart-canvas">
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart
              data={chartData}
              margin={{ top: 12, right: 8, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient
                  id={isCm ? "cmPriceFill" : "priceFill"}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop offset="0%" stopColor={seriesColor} stopOpacity={0.35} />
                  <stop
                    offset="100%"
                    stopColor={seriesColor}
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
                tickFormatter={(v) => `${tickPrefix}${Number(v).toFixed(2)}`}
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
                    ? formatMoney(value, moneyCur, 4)
                    : "—",
                  seriesName,
                ]}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="price"
                name={seriesName}
                stroke={seriesColor}
                strokeWidth={2.2}
                fill={`url(#${isCm ? "cmPriceFill" : "priceFill"})`}
                dot={false}
                connectNulls
                activeDot={{
                  r: 4,
                  fill: isCm ? "#8FA8C0" : "#D4A574",
                  stroke: "#121212",
                  strokeWidth: 2,
                }}
              />
              {!isCm &&
              predictedPrice != null &&
              Number.isFinite(predictedPrice) ? (
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
      ) : null}
    </div>
  );
}

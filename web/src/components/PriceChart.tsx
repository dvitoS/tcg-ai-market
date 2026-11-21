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
type ChartCondition = "NM" | "LP" | "MP";

const RANGES: { key: RangeKey; label: string; days: number | null }[] = [
  { key: "1m", label: "1M", days: 30 },
  { key: "3m", label: "3M", days: 90 },
  { key: "1y", label: "1Y", days: 365 },
  { key: "all", label: "All", days: null },
];

const CONDITIONS: ChartCondition[] = ["NM", "LP", "MP"];

const CHART_COLOR = "#B87333";
const CM_CHART_COLOR = "#5B7C99";

const DAY_MS = 24 * 60 * 60 * 1000;

function pointTs(date: string): number {
  return new Date(`${date}T00:00:00Z`).getTime();
}

/** Drop junk that collapses the Y domain (≤0 / NaN). */
function sanitizePoints(points: HistoryPoint[]): HistoryPoint[] {
  return points.filter((p) => {
    const price = Number(p.price);
    return Boolean(p.date) && Number.isFinite(price) && price > 0;
  });
}

function clipPoints(points: HistoryPoint[], range: RangeKey): HistoryPoint[] {
  const cfg = RANGES.find((r) => r.key === range);
  if (!cfg?.days || points.length === 0) return points;
  const last = pointTs(points[points.length - 1].date);
  const cutoff = last - cfg.days * DAY_MS;
  return points.filter((p) => pointTs(p.date) >= cutoff);
}

/** Full selected window ending at the last point — short history leaves empty left pad. */
function rangeDomainMs(
  points: HistoryPoint[],
  range: RangeKey,
): [number, number] | ["dataMin", "dataMax"] {
  if (!points.length) return ["dataMin", "dataMax"];
  const last = pointTs(points[points.length - 1].date);
  const first = pointTs(points[0].date);
  const cfg = RANGES.find((r) => r.key === range);
  if (cfg?.days) {
    return [last - cfg.days * DAY_MS, last];
  }
  return [first, last];
}

function coverageDays(points: HistoryPoint[]): number {
  if (!points.length) return 0;
  if (points.length === 1) return 1;
  const first = pointTs(points[0].date);
  const last = pointTs(points[points.length - 1].date);
  return Math.max(1, Math.round((last - first) / DAY_MS) + 1);
}

function shortDate(value: string, locale: string): string {
  const d = new Date(`${value}T00:00:00Z`);
  return d.toLocaleDateString(locale === "hr" ? "hr-HR" : "en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function shortDateFromTs(ts: number, locale: string): string {
  return shortDate(new Date(ts).toISOString().slice(0, 10), locale);
}

/** Break the stroke across long missing stretches so 1Y doesn't invent a ramp. */
const GAP_BREAK_DAYS = 14;

function toChartRows(
  points: HistoryPoint[],
  locale: string,
): Array<Record<string, string | number | null>> {
  const rows: Array<Record<string, string | number | null>> = [];
  for (let i = 0; i < points.length; i += 1) {
    const p = points[i];
    const ts = pointTs(p.date);
    if (i > 0) {
      const prevTs = pointTs(points[i - 1].date);
      const gapDays = (ts - prevTs) / DAY_MS;
      if (gapDays > GAP_BREAK_DAYS) {
        rows.push({
          date: "",
          label: "",
          ts: prevTs + Math.min(gapDays, GAP_BREAK_DAYS) * DAY_MS * 0.5,
          price: null,
        });
      }
    }
    rows.push({
      date: p.date,
      label: shortDate(p.date, locale),
      ts,
      price: Number(p.price),
    });
  }
  return rows;
}

function preferredFinish(finishes: string[]): string | null {
  if (!finishes.length) return null;
  const rank = (f: string) => {
    const v = f.toLowerCase();
    if (v.includes("reverse")) return 20;
    if (v.includes("holo") || v === "foil") return 0;
    if (v === "normal") return 10;
    return 40;
  };
  return [...finishes].sort((a, b) => rank(a) - rank(b))[0] ?? null;
}

export function PriceChart({
  cardId,
  points,
  predictedPrice,
  finishes = [],
}: {
  cardId?: string;
  points: HistoryPoint[];
  predictedPrice?: number | null;
  finishes?: string[];
}) {
  const { t, locale } = useLocale();
  const finishOptions = useMemo(
    () => finishes.filter(Boolean),
    [finishes],
  );
  const hintFinish = useMemo(
    () => preferredFinish(finishOptions),
    [finishOptions],
  );
  const [range, setRange] = useState<RangeKey>("1y");
  const [market, setMarket] = useState<MarketSource>("tcgplayer");
  // null = Soft Ink auto (DB / JustTCG / Pkmn with Holofoil preference) — no finish filter credit burn.
  const [finish, setFinish] = useState<string | null>(null);
  const [condition, setCondition] = useState<ChartCondition>("NM");
  const [sources, setSources] = useState<CardPriceSourcesResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(cardId) && points.length === 0);
  const [error, setError] = useState<string | null>(null);
  const [cmTried, setCmTried] = useState(false);
  const [cmLoading, setCmLoading] = useState(false);

  useEffect(() => {
    setFinish(null);
    setCondition("NM");
  }, [cardId]);

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
    fetchCardPriceSources(cardId, {
      grades: "none",
      limit: 400,
      printing: finish,
      condition: condition === "NM" ? null : condition,
    })
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
  }, [cardId, points.length, finish, condition]);

  // Lazy Cardmarket EUR series — only when the CM tab opens (PkmnPrices credits).
  // Do NOT depend on `sources` object identity: merging CM into sources used to
  // re-fire this effect, cancel the in-flight fetch, skip finally, and leave
  // "Loading Cardmarket prices…" forever (cmTried true + cmLoading true).
  const sourcesReady = sources != null;
  const cmHave =
    (sources?.cardmarket?.length ?? 0) > 0 ||
    Boolean(sources?.cardmarket_error);
  useEffect(() => {
    if (!cardId || market !== "cardmarket" || !sourcesReady || cmTried) return;
    if (cmHave) {
      setCmTried(true);
      return;
    }
    let cancelled = false;
    setCmLoading(true);
    const ac = new AbortController();
    // PkmnPrices client timeout is 30s; abort slightly after so the API can answer first.
    const timeoutId = window.setTimeout(() => ac.abort(), 35_000);
    fetchCardPriceSources(cardId, {
      grades: "none",
      limit: 400,
      cardmarket: true,
      printing: finish,
      condition: condition === "NM" ? null : condition,
      signal: ac.signal,
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
        const aborted =
          (err instanceof DOMException && err.name === "AbortError") ||
          (err instanceof Error && /abort/i.test(err.message));
        setSources((prev) =>
          prev
            ? {
                ...prev,
                cardmarket: prev.cardmarket ?? [],
                cardmarket_error: aborted
                  ? t("chart_cm_timeout")
                  : err instanceof Error
                    ? err.message
                    : t("chart_cm_failed"),
              }
            : prev,
        );
      })
      .finally(() => {
        window.clearTimeout(timeoutId);
        if (cancelled) return;
        setCmTried(true);
        setCmLoading(false);
      });
    return () => {
      cancelled = true;
      ac.abort();
      window.clearTimeout(timeoutId);
      setCmLoading(false);
    };
  }, [
    cardId,
    market,
    sourcesReady,
    cmHave,
    cmTried,
    finish,
    condition,
    t,
  ]);

  // Prefer live Soft Ink series, else DB / SSR history (TCGplayer-linked).
  // Non-NM must not fall back to NM DB points — that would lie about condition.
  const nmAll =
    condition !== "NM"
      ? sources?.justtcg?.length
        ? sources.justtcg
        : []
      : sources?.justtcg?.length
        ? sources.justtcg
        : sources?.tcgplayer?.length
          ? sources.tcgplayer
          : points;

  const cmAll = sources?.cardmarket?.length ? sources.cardmarket : [];
  const activeAll = market === "cardmarket" ? cmAll : nmAll;
  const clipped = useMemo(
    () => clipPoints(sanitizePoints(activeAll), range),
    [activeAll, range],
  );
  const chartData = useMemo(
    () => toChartRows(clipped, locale),
    [clipped, locale],
  );
  const xDomain = useMemo(
    () => rangeDomainMs(clipped, range),
    [clipped, range],
  );
  const rangeWantDays = RANGES.find((r) => r.key === range)?.days ?? null;
  const coveredDays = coverageDays(clipped);
  const coverageNote =
    rangeWantDays != null &&
    clipped.length > 0 &&
    coveredDays < Math.floor(rangeWantDays * 0.85)
      ? t("chart_coverage_short", {
          days: String(coveredDays),
          want: String(rangeWantDays),
        })
      : null;

  const isCm = market === "cardmarket";
  const seriesColor = isCm ? CM_CHART_COLOR : CHART_COLOR;
  const seriesName = isCm
    ? t("chart_series_cm_cond", { condition })
    : t("chart_series_tcg_cond", { condition });
  const moneyCur = isCm ? "EUR" : "USD";
  const tickPrefix = isCm ? "€" : "$";

  const cmEmpty =
    isCm &&
    !cmLoading &&
    !loading &&
    chartData.length === 0 &&
    cmTried;
  const usEmpty =
    !isCm &&
    !loading &&
    chartData.length === 0 &&
    (sources != null || Boolean(error));
  const usBudgetNote =
    // Hardcoded NM copy — never show it while LP/MP is selected.
    !isCm && condition === "NM" && sources?.justtcg_from_db
      ? t("chart_just_from_db")
      : !isCm && condition === "NM" && sources?.justtcg_fallback
        ? t("chart_just_fallback")
        : null;
  const usError =
    !isCm && sources?.justtcg_error
      ? sources.justtcg_error
      : !isCm && sources?.pkmnprices_error
        ? sources.pkmnprices_error
        : !isCm && error
          ? error
          : null;

  return (
    <div className="chart-panel">
      <div className="chart-head chart-head-mkt">
        <div>
          <h2>{t("chart_title")}</h2>
          {!isCm ? (
            <p className="chart-head-note">{t("chart_us_only_note")}</p>
          ) : (
            <p className="chart-head-note">{t("chart_cm_only_note")}</p>
          )}
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

      <div className="chart-filter-row">
        <div
          className="range-toggle chart-condition-toggle"
          role="tablist"
          aria-label={t("chart_condition_tabs")}
        >
          {CONDITIONS.map((item) => (
            <button
              key={item}
              type="button"
              role="tab"
              aria-selected={condition === item}
              className={condition === item ? "is-active" : ""}
              onClick={() => setCondition(item)}
            >
              {item}
            </button>
          ))}
        </div>
        {finishOptions.length > 1 ? (
          <div
            className="range-toggle chart-finish-toggle"
            role="tablist"
            aria-label={t("chart_finish_tabs")}
          >
            <button
              type="button"
              role="tab"
              aria-selected={finish == null}
              className={finish == null ? "is-active" : ""}
              onClick={() => setFinish(null)}
              title={
                hintFinish
                  ? t("chart_finish_auto_hint", { finish: hintFinish })
                  : undefined
              }
            >
              {t("chart_finish_auto")}
            </button>
            {finishOptions.map((item) => (
              <button
                key={item}
                type="button"
                role="tab"
                aria-selected={finish === item}
                className={finish === item ? "is-active" : ""}
                onClick={() => setFinish(item)}
              >
                {item}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {loading || cmLoading ? (
        <p className="chart-sources-status">
          {cmLoading ? t("chart_cm_loading") : t("chart_loading")}
        </p>
      ) : null}
      {error ? (
        <p className="chart-sources-status">{t("chart_fallback", { error })}</p>
      ) : null}
      {usBudgetNote && chartData.length > 0 ? (
        <p className="chart-sources-status">{usBudgetNote}</p>
      ) : null}
      {coverageNote ? (
        <p className="chart-sources-status">{coverageNote}</p>
      ) : null}
      {usError && chartData.length > 0 ? (
        <p className="chart-sources-status">{usError}</p>
      ) : null}
      {isCm && sources?.cardmarket_error && chartData.length === 0 && !cmLoading ? (
        <div className="chart-market-empty">
          <p className="chart-market-empty-title">{t("chart_cm_error_title")}</p>
          <p className="chart-market-empty-lede">{sources.cardmarket_error}</p>
        </div>
      ) : null}
      {usEmpty && usError ? (
        <div className="chart-market-empty">
          <p className="chart-market-empty-title">{t("chart_us_error_title")}</p>
          <p className="chart-market-empty-lede">{usError}</p>
        </div>
      ) : null}
      {usEmpty && !usError ? (
        <div className="chart-market-empty">
          <p className="chart-market-empty-title">{t("chart_empty")}</p>
          <p className="chart-market-empty-lede">{t("chart_us_empty_lede")}</p>
        </div>
      ) : null}

      {cmEmpty && !sources?.cardmarket_error ? (
        <div className="chart-market-empty">
          <p className="chart-market-empty-title">{t("chart_cm_empty_title")}</p>
          <p className="chart-market-empty-lede">{t("chart_cm_empty_lede")}</p>
        </div>
      ) : !cmEmpty &&
        !usEmpty &&
        !(isCm && chartData.length === 0 && cmLoading) &&
        chartData.length > 0 ? (
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
                dataKey="ts"
                type="number"
                scale="time"
                domain={xDomain}
                tick={{ fill: "#a1a1aa", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                minTickGap={36}
                tickFormatter={(ts) =>
                  typeof ts === "number" ? shortDateFromTs(ts, locale) : ""
                }
              />
              <YAxis
                tick={{ fill: "#a1a1aa", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                width={56}
                tickFormatter={(v) => `${tickPrefix}${Number(v).toFixed(2)}`}
                domain={[0, "auto"]}
                allowDataOverflow={false}
              />
              <Tooltip
                contentStyle={{
                  background: "#1a1a1a",
                  border: "1px solid #2a2a2a",
                  borderRadius: 10,
                  color: "#f4f4f5",
                }}
                labelStyle={{ color: "#a1a1aa" }}
                labelFormatter={(_, payload) => {
                  const row = payload?.[0]?.payload as
                    | { date?: string }
                    | undefined;
                  return row?.date
                    ? shortDate(row.date, locale)
                    : "";
                }}
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
                connectNulls={false}
                activeDot={{
                  r: 4,
                  fill: isCm ? "#8FA8C0" : "#D4A574",
                  stroke: "#121212",
                  strokeWidth: 2,
                }}
              />
              {!isCm &&
              condition === "NM" &&
              predictedPrice != null &&
              Number.isFinite(predictedPrice) ? (
                <ReferenceLine
                  y={predictedPrice}
                  stroke="#a1a1aa"
                  strokeDasharray="4 4"
                  label={{
                    value: `AI fair ${formatMoney(predictedPrice, "USD", 2)}`,
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

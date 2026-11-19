"use client";

import { useEffect, useState } from "react";

import { GRADED_AUTO_MIN_USD } from "@/components/GradedPriceChart";
import { useLocale } from "@/components/LocaleProvider";
import {
  MarketSourceTabs,
  type MarketSource,
} from "@/components/MarketSourceTabs";
import { fetchCardMarketComps, formatMoney } from "@/lib/api";
import type { MessageKey } from "@/lib/i18n/messages";
import type { CardMarketCompsResponse } from "@/lib/types";

function gradeLabel(
  grade: string,
  t: (key: MessageKey, params?: Record<string, string | number>) => string,
) {
  if (grade === "below_7") return t("comps_pop_below7");
  return grade;
}

export function MarketCompsPanel({
  cardId,
  nmSpotUsd,
  focus = "sold",
}: {
  cardId: string;
  nmSpotUsd?: number | null;
  /** Collectr stack: sold listings vs population-only mode. */
  focus?: "sold" | "population";
}) {
  const { t } = useLocale();
  const autoArm =
    nmSpotUsd != null &&
    Number.isFinite(Number(nmSpotUsd)) &&
    Number(nmSpotUsd) >= GRADED_AUTO_MIN_USD;

  const [armed, setArmed] = useState(autoArm || focus === "population");
  const [market, setMarket] = useState<MarketSource>("ebay");
  const [data, setData] = useState<CardMarketCompsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setArmed(autoArm || focus === "population");
    setData(null);
    setError(null);
    setLoading(false);
    setMarket("ebay");
  }, [cardId, autoArm, focus]);

  useEffect(() => {
    if (!armed) return;
    let alive = true;
    setLoading(true);
    setError(null);
    void fetchCardMarketComps(cardId, 10)
      .then((payload) => {
        if (!alive) return;
        setData(payload);
      })
      .catch((err) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : t("comps_error"));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [armed, cardId, t]);

  const ebay = data?.ebay_sold || [];
  const ebayStats = data?.ebay_sold_stats;
  const cm = data?.cardmarket || [];
  const cmStats = data?.cardmarket_stats;
  const pop = data?.population;
  const gradeRows = pop?.grade_rows || [];

  const titleByMarket: Record<MarketSource, string> = {
    ebay: t("comps_sold_title_ebay"),
    tcgplayer: t("comps_sold_title_tcp"),
    cardmarket: t("comps_sold_title_cm"),
  };

  if (focus === "population") {
    return (
      <section className="comps-panel comps-panel-pop" aria-label={t("comps_pop_title")}>
        <div className="comps-head">
          <h2>{t("comps_pop_title")}</h2>
          <p>{t("comps_pop_lede")}</p>
        </div>
        {loading ? (
          <p className="chart-sources-status">{t("comps_loading")}</p>
        ) : null}
        {error && !data ? <p className="form-error">{error}</p> : null}
        {data?.population_error && !pop ? (
          <p className="chart-sources-status">{data.population_error}</p>
        ) : null}
        {pop ? (
          <div className="comps-block comps-block-pop">
            <div className="comps-stats">
              <div>
                <span>{t("comps_pop_total")}</span>
                <strong>
                  {pop.total_population != null
                    ? String(pop.total_population)
                    : "—"}
                </strong>
              </div>
              <div>
                <span>{t("comps_pop_gems")}</span>
                <strong>
                  {pop.total_gems != null ? String(pop.total_gems) : "—"}
                  {pop.gem_rate != null
                    ? ` · ${pop.gem_rate.toFixed(1)}%`
                    : ""}
                </strong>
              </div>
              <div>
                <span>{t("comps_pop_variant")}</span>
                <strong>{pop.variant || "—"}</strong>
              </div>
            </div>
            {pop.gem_rate != null ? (
              <p className="comps-gem-callout">
                {t("comps_pop_gem_callout", {
                  rate: pop.gem_rate.toFixed(1),
                })}
              </p>
            ) : null}
            {gradeRows.length > 0 ? (
              <table className="comps-pop-table">
                <thead>
                  <tr>
                    <th>{t("comps_pop_grade")}</th>
                    <th>{t("comps_pop_count")}</th>
                    <th>{t("comps_pop_share")}</th>
                    <th>{t("comps_pop_higher")}</th>
                  </tr>
                </thead>
                <tbody>
                  {gradeRows.map((row) => (
                    <tr key={row.grade}>
                      <td>{gradeLabel(row.grade, t)}</td>
                      <td>{row.count}</td>
                      <td>
                        {row.share_pct != null
                          ? `${row.share_pct.toFixed(1)}%`
                          : "—"}
                      </td>
                      <td>
                        {row.percent_higher != null
                          ? `${row.percent_higher.toFixed(1)}%`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
            {pop.pop_report_url ? (
              <p className="comps-pop-link">
                <a
                  href={pop.pop_report_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {t("comps_pop_psa_link")}
                </a>
              </p>
            ) : null}
          </div>
        ) : !loading && data && !data.population_error ? (
          <p className="chart-sources-status">{t("comps_pop_empty")}</p>
        ) : null}
      </section>
    );
  }

  return (
    <section className="comps-panel" aria-label={t("comps_title")}>
      <div className="comps-head comps-head-mkt">
        <div>
          <h2>{titleByMarket[market]}</h2>
          <p>
            {autoArm
              ? t("comps_subtitle_auto", { min: String(GRADED_AUTO_MIN_USD) })
              : t("comps_subtitle")}
          </p>
        </div>
        <MarketSourceTabs
          sources={["ebay", "tcgplayer", "cardmarket"]}
          value={market}
          onChange={setMarket}
          ariaLabel={t("comps_market_tabs")}
        />
      </div>

      {!armed ? (
        <p className="grade-ev-idle">
          <button
            type="button"
            className="btn-primary"
            onClick={() => setArmed(true)}
          >
            {t("comps_load")}
          </button>
          <span className="lot-meta">{t("comps_load_hint")}</span>
        </p>
      ) : null}

      {armed && loading ? (
        <p className="chart-sources-status">{t("comps_loading")}</p>
      ) : null}
      {armed && error && !data ? (
        <p className="form-error">{error}</p>
      ) : null}

      {armed && data ? (
        <div className="comps-body">
          {market === "ebay" ? (
            <div className="comps-block">
              <p className="comps-lede">{t("comps_ebay_lede")}</p>
              {data.ebay_error && ebay.length === 0 ? (
                <p className="chart-sources-status">{data.ebay_error}</p>
              ) : null}
              {ebayStats?.n ? (
                <div className="comps-stats">
                  <div>
                    <span>{t("comps_median")}</span>
                    <strong>
                      {formatMoney(
                        ebayStats.median,
                        ebayStats.currency || "USD",
                        2,
                      )}
                    </strong>
                  </div>
                  <div>
                    <span>{t("comps_range")}</span>
                    <strong>
                      {formatMoney(ebayStats.low, "USD", 2)} –{" "}
                      {formatMoney(ebayStats.high, "USD", 2)}
                    </strong>
                  </div>
                  <div>
                    <span>{t("comps_n")}</span>
                    <strong>{ebayStats.n}</strong>
                  </div>
                </div>
              ) : null}
              {ebay.length === 0 && !data.ebay_error ? (
                <p className="chart-sources-status">{t("comps_ebay_empty")}</p>
              ) : null}
              <ul className="comps-list">
                {ebay.slice(0, 8).map((row, i) => (
                  <li key={`ebay-${i}`}>
                    <span className="comps-list-meta">
                      {[row.date, row.condition].filter(Boolean).join(" · ") ||
                        "—"}
                    </span>
                    <strong>
                      {formatMoney(row.price, row.currency || "USD", 2)}
                    </strong>
                    {row.url ? (
                      <a
                        href={row.url}
                        target="_blank"
                        rel="noopener noreferrer sponsored"
                      >
                        eBay ↗
                      </a>
                    ) : (
                      <span className="ebay-link-muted">—</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {market === "tcgplayer" ? (
            <div className="comps-block">
              <p className="comps-lede">{t("comps_tcp_lede")}</p>
              <p className="chart-sources-status">{t("comps_tcp_empty")}</p>
            </div>
          ) : null}

          {market === "cardmarket" ? (
            <div className="comps-block">
              <p className="comps-lede">{t("comps_cm_lede")}</p>
              {data.cardmarket_error && cm.length === 0 ? (
                <p className="chart-sources-status">{data.cardmarket_error}</p>
              ) : null}
              {cmStats?.lowest != null ? (
                <div className="comps-stats">
                  <div>
                    <span>{t("comps_lowest")}</span>
                    <strong>{formatMoney(cmStats.lowest, "EUR", 2)}</strong>
                  </div>
                  <div>
                    <span>{t("comps_n")}</span>
                    <strong>{cmStats.n}</strong>
                  </div>
                </div>
              ) : null}
              {cm.length === 0 && !data.cardmarket_error ? (
                <p className="chart-sources-status">{t("comps_cm_empty")}</p>
              ) : null}
              <ul className="comps-list">
                {cm.slice(0, 8).map((row, i) => (
                  <li key={`cm-${i}`}>
                    <span className="comps-list-meta">
                      {[
                        row.condition,
                        row.variant,
                        row.seller_country,
                        row.seller,
                      ]
                        .filter(Boolean)
                        .join(" · ") || "—"}
                    </span>
                    <strong>{formatMoney(row.price, "EUR", 2)}</strong>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

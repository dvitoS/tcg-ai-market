"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AddLotForm } from "@/components/AddLotForm";
import { useCurrency } from "@/components/CurrencyProvider";
import { DeferredMount } from "@/components/DeferredMount";
import { EbayComps } from "@/components/EbayComps";
import { GradingEvPanel } from "@/components/GradingEvPanel";
import { HoloCardArt } from "@/components/HoloCardArt";
import { useLocale } from "@/components/LocaleProvider";
import { PriceChart } from "@/components/PriceChart";
import { WatchToggle } from "@/components/WatchToggle";
import { WrongSpotReport } from "@/components/WrongSpotReport";
import { fetchCardDetail, formatChange } from "@/lib/api";
import { readBrowseReturn } from "@/lib/browseReturn";
import { resolveCardImageUrl } from "@/lib/cardImage";
import { cardmarketSearchUrl } from "@/lib/cardmarket";
import { resolveFoilMode } from "@/lib/foilMode";
import { decisionOneLiner, signalLabel } from "@/lib/i18n/messages";
import type { CardDetailResponse, HistoryPoint } from "@/lib/types";

function deltaClass(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "flat";
  if (value > 0.05) return "up";
  if (value < -0.05) return "down";
  return "flat";
}

function signalClass(signal?: string | null): string {
  const key = (signal || "").toUpperCase();
  if (key === "BUY") return "signal-buy";
  if (key === "SELL") return "signal-sell";
  return "signal-hold";
}

export function CardDetailView({
  detail,
  points,
}: {
  detail: CardDetailResponse;
  points: HistoryPoint[];
}) {
  const { locale, t } = useLocale();
  const router = useRouter();
  const { formatSpot, currency, usdEur, fxFallback } = useCurrency();
  const { card, pred_lo_pct, pred_hi_pct, explain } = detail;
  const [finishes, setFinishes] = useState<string[]>(
    () => (card.finishes || []).filter(Boolean),
  );
  const [browseBackHref, setBrowseBackHref] = useState("/browse");

  useEffect(() => {
    setBrowseBackHref(readBrowseReturn("/browse"));
  }, []);

  // Soft Ink client nav can land with empty finishes; refetch only then.
  const finishesKey = (card.finishes || []).join("|");
  useEffect(() => {
    const initial = (card.finishes || []).filter(Boolean);
    setFinishes(initial);
    if (initial.length > 0) return;
    let alive = true;
    void fetchCardDetail(card.id)
      .then((fresh) => {
        if (!alive) return;
        const next = (fresh.card.finishes || []).filter(Boolean);
        if (next.length) setFinishes(next);
      })
      .catch(() => {
        /* keep SSR / rarity foil */
      });
    return () => {
      alive = false;
    };
    // finishesKey tracks SSR payload changes without array identity churn.
  }, [card.id, card.finishes, finishesKey]);

  const prices = points.map((p) => p.price).filter((n) => Number.isFinite(n));
  const fromPoints = {
    points: points.length,
    min_price: prices.length ? Math.min(...prices) : null,
    max_price: prices.length ? Math.max(...prices) : null,
    last_price: prices.length ? prices[prices.length - 1] : card.price ?? null,
    previous_price: prices.length > 1 ? prices[prices.length - 2] : null,
    day_change_pct:
      prices.length > 1 && prices[prices.length - 2]
        ? ((prices[prices.length - 1] - prices[prices.length - 2]) /
            prices[prices.length - 2]) *
          100
        : null,
    first_date: points[0]?.date ?? null,
    last_date: points[points.length - 1]?.date ?? null,
  };
  const history = {
    ...fromPoints,
    ...(detail.history || {}),
    min_price: detail.history?.min_price ?? fromPoints.min_price,
    max_price: detail.history?.max_price ?? fromPoints.max_price,
    last_price: detail.history?.last_price ?? fromPoints.last_price,
    day_change_pct: detail.history?.day_change_pct ?? fromPoints.day_change_pct,
    points: detail.history?.points || fromPoints.points,
  };
  const foil = resolveFoilMode(finishes, card.rarity, card.name);
  const meta = [card.set_name, card.rarity, card.id].filter(Boolean).join(" · ");
  const image = resolveCardImageUrl(card.id, card.image_url);
  const dayChange = history.day_change_pct;
  const showSignal = Boolean(card.confidence_ok && card.conformal_ok && card.signal);
  const band =
    pred_lo_pct != null && pred_hi_pct != null
      ? `${formatChange(pred_lo_pct, 1)} … ${formatChange(pred_hi_pct, 1)}`
      : null;
  const signalText = signalLabel(locale, card.signal);
  const signalKey = (card.signal || "").toUpperCase();
  const detailSide =
    signalKey === "BUY" || signalKey === "KUPI"
      ? "UNDER"
      : signalKey === "SELL" || signalKey === "PRODAJ"
        ? "OVER"
        : null;
  const decision =
    showSignal && detailSide
      ? decisionOneLiner(locale, detailSide, card.expected_change_pct)
      : null;

  return (
    <article className="detail-page">
      <Link
        href={browseBackHref}
        className="detail-back"
        onClick={(event) => {
          // Prefer history when we came from the same Soft Ink browse search.
          try {
            const ref = document.referrer ? new URL(document.referrer) : null;
            if (
              ref &&
              ref.origin === window.location.origin &&
              ref.pathname.startsWith("/browse")
            ) {
              event.preventDefault();
              router.back();
            }
          } catch {
            /* follow href */
          }
        }}
      >
        {t("detail_back")}
      </Link>

      <div className="detail-layout">
        <div className="detail-main">
          <section className="detail-hero-card">
            <div className="detail-hero-left">
              <div className="detail-hero-art">
                <HoloCardArt
                  key={`${card.id}-${foil || "none"}`}
                  cardId={card.id}
                  name={card.name}
                  image={image}
                  foil={foil}
                  priority
                />
              </div>
              <aside className="detail-hero-under" aria-label={t("detail_ai_under_title")}>
                <p className="detail-under-label">{t("detail_ai_under_title")}</p>
                <p className={`detail-under-move ${deltaClass(card.expected_change_pct)}`}>
                  {formatChange(card.expected_change_pct, 2)}
                </p>
                <p className="detail-under-price">
                  {t("detail_predicted")}: {formatSpot(card.predicted_price, 2)}
                </p>
                {band ? (
                  <p className="detail-under-caption" title={t("glossary_band_tip")}>
                    {t("detail_band", { band })}
                  </p>
                ) : (
                  <p className="detail-under-caption">{t("detail_horizon")}</p>
                )}
                {decision ? (
                  <p className="decision-line">{decision}</p>
                ) : showSignal ? (
                  <div className={`signal-chip ${signalClass(card.signal)}`}>
                    {signalText}
                  </div>
                ) : (
                  <div className="ai-low-conf" title={t("glossary_unsure_tip")}>
                    {t("detail_low_conf")}
                  </div>
                )}
                <p className="detail-desk-disclaimer">{t("detail_desk_disclaimer")}</p>
                <WrongSpotReport
                  cardId={card.id}
                  spot={history.last_price ?? card.price}
                />
              </aside>
            </div>
            <div className="detail-hero-copy">
              <h1 className="detail-name">{card.name}</h1>
              <p className="detail-meta">{meta}</p>
              {finishes.length > 0 ? (
                <p className="detail-finishes" title={t("detail_finishes_hint")}>
                  {t("detail_finishes", { finishes: finishes.join(" · ") })}
                </p>
              ) : null}
              {foil === "holo" ? (
                <p className="detail-foil-tip">{t("detail_foil_holo")}</p>
              ) : foil === "reverse" ? (
                <p className="detail-foil-tip">{t("detail_foil_reverse")}</p>
              ) : null}
              <div className="detail-price">
                {formatSpot(history.last_price ?? card.price, 2)}
              </div>
              <p className="detail-spot-source">
                {history.last_date
                  ? t("detail_spot_source_asof", { date: history.last_date })
                  : t("detail_spot_source")}
              </p>
              {currency === "EUR" && usdEur != null ? (
                <p className="detail-fx-note" title={fxFallback ? t("fx_fallback") : undefined}>
                  {t("fx_rate_tip", { rate: usdEur.toFixed(4) })}
                  {" · "}
                  {t("detail_fx_not_eu")}
                </p>
              ) : (
                <p className="detail-fx-note">{t("detail_eu_separate")}</p>
              )}
              <div className={`detail-hero-delta ${deltaClass(dayChange)}`}>
                {formatChange(dayChange, 2)}
              </div>
              <div className="detail-actions">
                <WatchToggle cardId={card.id} />
                <Link
                  href={`/trade?add=${encodeURIComponent(card.id)}&side=you`}
                  className="btn-primary"
                >
                  {t("detail_trade_you")}
                </Link>
                <a
                  className="btn-ghost"
                  href={cardmarketSearchUrl(card.name, card.set_name)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {t("detail_cardmarket")}
                </a>
                <details className="detail-actions-more">
                  <summary>{t("detail_more")}</summary>
                  <div className="detail-actions-more-menu">
                    <Link href="/portfolio#watchlist" className="btn-ghost">
                      {t("detail_watchlist")}
                    </Link>
                    <Link
                      href={`/trade?add=${encodeURIComponent(card.id)}&side=them`}
                      className="btn-ghost"
                    >
                      {t("detail_trade_them")}
                    </Link>
                  </div>
                </details>
              </div>
              <div className="stat-row">
                <div className="stat-chip">
                  <span>{t("detail_range_min")}</span>
                  <strong>{formatSpot(history.min_price, 0)}</strong>
                </div>
                <div className="stat-chip">
                  <span>{t("detail_range_max")}</span>
                  <strong>{formatSpot(history.max_price, 0)}</strong>
                </div>
              </div>
              <AddLotForm
                cardId={card.id}
                cardName={card.name}
                defaultPrice={history.last_price ?? card.price}
              />
            </div>
          </section>

          {explain ? (
            <section className="detail-ai-board">
              <div className="detail-ai-head">
                <h2>{t("detail_why")}</h2>
              </div>
              <div className="ai-explain">
                <p className="ai-conf">
                  {t("detail_confidence", { level: explain.confidence_level })}
                  {explain.confidence_reason ? ` — ${explain.confidence_reason}` : ""}
                </p>
                {explain.rows.length > 0 ? (
                  <dl className="ai-explain-list">
                    {explain.rows.map((row) => (
                      <div key={row.label} className="ai-explain-row">
                        <dt>{row.label}</dt>
                        <dd>{row.value}</dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="ai-board-caption">{t("detail_explain_need")}</p>
                )}
              </div>
            </section>
          ) : null}
        </div>

        <aside className="detail-side">
          <PriceChart
            cardId={card.id}
            points={points}
            predictedPrice={card.predicted_price}
          />
          <DeferredMount>
            <GradingEvPanel
              cardId={card.id}
              rawPrice={history.last_price ?? card.price}
            />
            <EbayComps cardId={card.id} cardName={card.name} />
          </DeferredMount>
        </aside>
      </div>
    </article>
  );
}

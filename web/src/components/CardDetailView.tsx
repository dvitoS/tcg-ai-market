"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AddLotForm } from "@/components/AddLotForm";
import { useCurrency } from "@/components/CurrencyProvider";
import { DeferredMount } from "@/components/DeferredMount";
import { GradingEvPanel } from "@/components/GradingEvPanel";
import { HoloCardArt } from "@/components/HoloCardArt";
import { useLocale } from "@/components/LocaleProvider";
import { GradedPriceChart } from "@/components/GradedPriceChart";
import { MarketCompsPanel } from "@/components/MarketCompsPanel";
import { PriceChart } from "@/components/PriceChart";
import { WatchToggle } from "@/components/WatchToggle";
import { WrongSpotReport } from "@/components/WrongSpotReport";
import { fetchCardDetail, formatChange } from "@/lib/api";
import { readBrowseReturn } from "@/lib/browseReturn";
import { resolveCardImageUrl } from "@/lib/cardImage";
import { cardmarketSearchUrl } from "@/lib/cardmarket";
import { resolveDeskNumbers } from "@/lib/deskNumbers";
import { resolveFoilMode } from "@/lib/foilMode";
import { trackFunnel } from "@/lib/funnel";
import { decisionOneLiner, signalLabel } from "@/lib/i18n/messages";
import { absoluteUrl, cardPagePath } from "@/lib/seo";
import { tcgplayerSearchUrl } from "@/lib/tcgplayer";
import type { CardDetailResponse, HistoryPoint } from "@/lib/types";

type DeskMode = "raw" | "graded" | "pop";

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
  const [deskMode, setDeskMode] = useState<DeskMode>("raw");
  const [shareBusy, setShareBusy] = useState(false);
  const [shareNote, setShareNote] = useState<string | null>(null);

  useEffect(() => {
    setBrowseBackHref(readBrowseReturn("/browse"));
  }, []);

  useEffect(() => {
    setDeskMode("raw");
  }, [card.id]);

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
  }, [card.id, card.finishes, finishesKey]);

  const prices = points.map((p) => p.price).filter((n) => Number.isFinite(n));
  const fromPoints = {
    points: points.length,
    min_price: prices.length ? Math.min(...prices) : null,
    max_price: prices.length ? Math.max(...prices) : null,
    last_price: prices.length ? prices[prices.length - 1] : card.price ?? null,
    day_change_pct:
      prices.length > 1 && prices[prices.length - 2]
        ? ((prices[prices.length - 1] - prices[prices.length - 2]) /
            prices[prices.length - 2]) *
          100
        : null,
    last_date: points[points.length - 1]?.date ?? null,
  };
  const history = {
    ...fromPoints,
    ...(detail.history || {}),
    min_price: detail.history?.min_price ?? fromPoints.min_price,
    max_price: detail.history?.max_price ?? fromPoints.max_price,
    last_price: detail.history?.last_price ?? fromPoints.last_price,
    day_change_pct: detail.history?.day_change_pct ?? fromPoints.day_change_pct,
  };
  const foil = resolveFoilMode(finishes, card.rarity, card.name);
  const meta = ["Pokémon", card.set_name, card.rarity, card.id]
    .filter(Boolean)
    .join(" · ");
  const image = resolveCardImageUrl(card.id, card.image_url);
  const dayChange = history.day_change_pct;
  const matchQuality = detail.spot_match?.quality ?? null;
  const matchLow = matchQuality === "low";
  const showSignal = Boolean(
    card.confidence_ok && card.conformal_ok && card.signal && !matchLow,
  );
  const matchLabelKey =
    matchQuality === "high"
      ? "detail_match_high"
      : matchQuality === "med"
        ? "detail_match_med"
        : matchQuality === "low"
          ? "detail_match_low"
          : null;
  const matchTipKey =
    matchQuality === "high"
      ? "detail_match_high_tip"
      : matchQuality === "med"
        ? "detail_match_med_tip"
        : matchQuality === "low"
          ? "detail_match_low_tip"
          : null;
  const spotFixed = detail.spot_report?.status === "resolved";
  const band =
    pred_lo_pct != null && pred_hi_pct != null
      ? `${formatChange(pred_lo_pct, 1)} … ${formatChange(pred_hi_pct, 1)}`
      : null;
  const signalText = signalLabel(locale, card.signal);
  const signalKey = (card.signal || "").toUpperCase();
  const signalSide =
    signalKey === "BUY" || signalKey === "KUPI"
      ? "UNDER"
      : signalKey === "SELL" || signalKey === "PRODAJ"
        ? "OVER"
        : null;
  const desk = resolveDeskNumbers({
    lastPrice: history.last_price,
    price: card.price,
    predicted_price: card.predicted_price,
    side: signalSide,
  });
  const askSpot = desk.asking;
  const gapPct = desk.edgeGapPct;
  const detailSide = desk.side ?? signalSide;
  /** Soft Ink desks show the 30d model only — no 7d prediction fallback. */
  const move30d =
    card.expected_change_30d_pct != null &&
    Number.isFinite(Number(card.expected_change_30d_pct))
      ? Number(card.expected_change_30d_pct)
      : null;
  const decision =
    showSignal && detailSide && gapPct != null
      ? decisionOneLiner(locale, detailSide, gapPct)
      : null;

  const verdictLine = decision
    ? decision
    : showSignal
      ? signalText
      : t("detail_low_conf");

  const modes: { key: DeskMode; label: string }[] = [
    { key: "raw", label: t("detail_mode_raw") },
    { key: "graded", label: t("detail_mode_graded") },
    { key: "pop", label: t("detail_mode_pop") },
  ];

  async function onCopyShare() {
    if (shareBusy) return;
    setShareBusy(true);
    setShareNote(null);
    const url = absoluteUrl(cardPagePath(card.id));
    const ask = formatSpot(askSpot, 2);
    const good =
      desk.good != null ? formatSpot(desk.good, 2) : null;
    const lines = [
      [card.name, card.set_name].filter(Boolean).join(" · "),
      verdictLine,
      good
        ? `${t("detail_asking")} ${ask} · ${t("detail_fair")} ${good}`
        : `${t("detail_asking")} ${ask}`,
      move30d != null ? `30d ${formatChange(move30d, 1)}` : null,
      url,
    ].filter(Boolean) as string[];
    const text = lines.join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setShareNote(t("detail_share_copied"));
      trackFunnel("share_copy", { surface: "detail", card_id: card.id });
    } catch {
      setShareNote(`${t("detail_share_copied_fallback")}\n${url}`);
    } finally {
      setShareBusy(false);
    }
  }

  return (
    <article className="detail-page detail-page-desk">
      <Link
        href={browseBackHref}
        className="detail-back"
        onClick={(event) => {
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

      {/* 1 — Hero identity */}
      <section className="detail-hero-band" aria-labelledby="detail-card-name">
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
        <div className="detail-hero-copy">
          <h1 id="detail-card-name" className="detail-name">
            {card.name}
          </h1>
          <p className="detail-meta">{meta}</p>

          <div className="detail-price-row">
            <div className="detail-price">
              {formatSpot(history.last_price ?? card.price, 2)}
            </div>
            <div className={`detail-hero-delta ${deltaClass(dayChange)}`}>
              {formatChange(dayChange, 2)}
            </div>
          </div>

          <p className="detail-asof">
            {history.last_date
              ? t("detail_spot_asof_chip", { date: history.last_date })
              : t("detail_spot_asof_today")}
          </p>

          <div className="detail-fair-row">
            <div className="detail-fair-cell">
              <span className="detail-fair-k">
                {t(currency === "EUR" ? "detail_asking_us" : "detail_asking")}
                {matchLabelKey && matchTipKey ? (
                  <span
                    className={`detail-match-badge is-${matchQuality}`}
                    title={t(matchTipKey)}
                  >
                    {t(matchLabelKey)}
                  </span>
                ) : null}
              </span>
              <span className="detail-fair-v">
                {formatSpot(history.last_price ?? card.price, 2)}
              </span>
            </div>
            <div className="detail-fair-cell">
              <span
                className="detail-fair-k"
                title={t("detail_fair_us_tip")}
              >
                {t(currency === "EUR" ? "detail_fair_us" : "detail_fair")}
              </span>
              <span className="detail-fair-v">
                {formatSpot(card.predicted_price, 2)}
              </span>
            </div>
          </div>
          {currency === "EUR" ? (
            <p className="detail-fx-asking-note" title={t("fx_rate_tip", { rate: (usdEur ?? 0).toFixed(4) })}>
              {t("detail_eur_is_fx")}
            </p>
          ) : null}

          {spotFixed ? (
            <p className="detail-spot-fixed" title={t("detail_spot_fixed_hint")}>
              {t("detail_spot_fixed")}
            </p>
          ) : null}

          <p
            className={`detail-verdict ${signalClass(card.signal)}${showSignal ? "" : " is-unsure"}`}
          >
            {verdictLine}
            {showSignal && move30d != null ? (
              <span className="detail-verdict-move">
                {" "}
                · {formatChange(move30d, 1)}
              </span>
            ) : null}
          </p>

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
            <a
              className="btn-ghost"
              href={tcgplayerSearchUrl(card.name, card.set_name)}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t("detail_tcgplayer")}
            </a>
            <button
              type="button"
              className="btn-ghost"
              disabled={shareBusy}
              onClick={() => void onCopyShare()}
            >
              {shareBusy ? t("detail_share_busy") : t("detail_share_copy")}
            </button>
          </div>
          {shareNote ? <p className="pro-open-note">{shareNote}</p> : null}
        </div>
      </section>

      {/* 2 — Raw | Graded | Pop. */}
      <div
        className="detail-mode-tabs"
        role="tablist"
        aria-label={t("detail_mode_tabs")}
      >
        {modes.map((mode) => (
          <button
            key={mode.key}
            type="button"
            role="tab"
            aria-selected={deskMode === mode.key}
            className={`detail-mode-tab${deskMode === mode.key ? " is-active" : ""}`}
            onClick={() => setDeskMode(mode.key)}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* 3 — Chart + sold under graph | side rail */}
      <div className="detail-desk-split">
        <div className="detail-desk-main">
          <section className="detail-section detail-section-chart">
            {deskMode === "raw" ? (
              <PriceChart
                cardId={card.id}
                points={points}
                predictedPrice={card.predicted_price}
                finishes={finishes}
              />
            ) : null}
            {deskMode === "graded" ? (
              <>
                <GradedPriceChart
                  cardId={card.id}
                  nmSpotUsd={history.last_price ?? card.price}
                />
                <div className="detail-graded-ev">
                  <h2 className="detail-side-heading">
                    {t("detail_grading_ev_fold")}
                  </h2>
                  <DeferredMount>
                    <GradingEvPanel
                      cardId={card.id}
                      rawPrice={history.last_price ?? card.price}
                    />
                  </DeferredMount>
                </div>
              </>
            ) : null}
            {deskMode === "pop" ? (
              <MarketCompsPanel
                cardId={card.id}
                cardName={card.name}
                setName={card.set_name}
                nmSpotUsd={history.last_price ?? card.price}
                focus="population"
              />
            ) : null}
          </section>

          <section className="detail-section detail-section-sold">
            <MarketCompsPanel
              cardId={card.id}
              cardName={card.name}
              setName={card.set_name}
              nmSpotUsd={history.last_price ?? card.price}
              focus="sold"
            />
          </section>
        </div>

        <aside className="detail-desk-side" aria-label={t("detail_side_rail")}>
          {explain ? (
            <details className="detail-fold detail-side-why">
              <summary className="detail-fold-summary">
                {t("detail_why")}
                <span className="detail-fold-meta">
                  {t("detail_confidence", { level: explain.confidence_level })}
                </span>
              </summary>
              <div className="detail-fold-body">
                {explain.confidence_reason ? (
                  <p className="ai-conf">{explain.confidence_reason}</p>
                ) : null}
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
            </details>
          ) : null}

          <div className="detail-side-module detail-side-lot">
            <h2 className="detail-side-heading">{t("detail_lot_fold")}</h2>
            <AddLotForm
              cardId={card.id}
              cardName={card.name}
              defaultPrice={history.last_price ?? card.price}
            />
          </div>
        </aside>
      </div>

      {/* Below fold extras — EV lives in Graded tab when that mode is open. */}
      <div className="detail-below">
        {deskMode !== "graded" ? (
          <DeferredMount>
            <details className="detail-fold">
              <summary className="detail-fold-summary">
                {t("detail_grading_ev_fold")}
              </summary>
              <div className="detail-fold-body">
                <GradingEvPanel
                  cardId={card.id}
                  rawPrice={history.last_price ?? card.price}
                />
              </div>
            </details>
          </DeferredMount>
        ) : null}

        <details className="detail-fold">
          <summary className="detail-fold-summary">
            {t("detail_details_fold")}
          </summary>
          <div className="detail-fold-body">
            {finishes.length > 0 ? (
              <p className="detail-finishes" title={t("detail_finishes_hint")}>
                {t("detail_finishes", { finishes: finishes.join(" · ") })}
              </p>
            ) : null}
            {band ? (
              <p className="detail-under-caption" title={t("glossary_band_tip")}>
                {t("detail_predicted")}: {formatSpot(card.predicted_price, 2)}
                {" · "}
                {t("detail_band", { band })}
              </p>
            ) : (
              <p className="detail-under-caption">
                {t("detail_predicted")}: {formatSpot(card.predicted_price, 2)}
              </p>
            )}
            {currency === "EUR" && usdEur != null ? (
              <p
                className="detail-fx-note"
                title={fxFallback ? t("fx_fallback") : undefined}
              >
                {t("fx_rate_tip", { rate: usdEur.toFixed(4) })}
              </p>
            ) : null}
            <p className="detail-desk-disclaimer">{t("detail_desk_disclaimer")}</p>
            <WrongSpotReport
              cardId={card.id}
              spot={history.last_price ?? card.price}
              initialReport={detail.spot_report ?? null}
            />
            <div className="detail-fold-actions">
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
          </div>
        </details>
      </div>
    </article>
  );
}

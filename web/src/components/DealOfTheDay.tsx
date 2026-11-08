"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useCurrency } from "@/components/CurrencyProvider";
import { DeskLoading } from "@/components/DeskLoading";
import { DotdShareExport } from "@/components/DotdShareExport";
import { useLocale } from "@/components/LocaleProvider";
import { fetchRadarPreview, formatChange } from "@/lib/api";
import { trackFunnel } from "@/lib/funnel";
import {
  decisionOneLiner,
  sideLabel,
  sideTipKey,
} from "@/lib/i18n/messages";
import type { RadarCard, RadarPreviewResponse } from "@/lib/types";

function bandLabel(card: RadarCard): string | null {
  const lo = card.pred_lo_pct;
  const hi = card.pred_hi_pct;
  if (lo == null || hi == null) return null;
  if (!Number.isFinite(Number(lo)) || !Number.isFinite(Number(hi))) return null;
  return `${formatChange(Number(lo), 1)}…${formatChange(Number(hi), 1)}`;
}

function TeaserRow({ card }: { card: RadarCard }) {
  const { t } = useLocale();
  const { formatSpot } = useCurrency();
  const fair = formatSpot(card.fair_price ?? card.predicted_price);
  const edge = formatChange(card.edge_pct);
  return (
    <Link
      href={`/cards/${encodeURIComponent(card.id)}`}
      className="scan-row radar-row radar-under"
    >
      <div className="scan-art">
        <Image
          src={card.image_url || "/kestrel-logo.png"}
          alt={card.name}
          width={48}
          height={67}
        />
      </div>
      <div>
        <div className="lot-name">{card.name}</div>
        <div className="lot-meta">
          {[card.set_name, card.rarity].filter(Boolean).join(" · ")}
        </div>
      </div>
      <div className="scan-metrics">
        <strong>{formatSpot(card.spot ?? card.price)}</strong>
        <span title={t("glossary_fair_tip")}>{t("metric_fair", { price: fair })}</span>
        <span className="pnl-up" title={t("glossary_edge_tip")}>
          {t("metric_edge", { pct: edge })}
        </span>
      </div>
    </Link>
  );
}

export function DealOfTheDay({
  limit = 1,
  variant = "landing",
  className = "",
  initialPreview = null,
}: {
  limit?: number;
  variant?: "landing" | "pro";
  className?: string;
  /** SSR / parent-provided preview — skips the cold client fetch when present. */
  initialPreview?: RadarPreviewResponse | null;
}) {
  const { t, locale } = useLocale();
  const { formatSpot } = useCurrency();
  const [preview, setPreview] = useState<RadarPreviewResponse | null>(
    initialPreview,
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!initialPreview);

  const capped = Math.max(1, Math.min(8, Math.floor(limit) || 1));

  useEffect(() => {
    // Trust SSR payload for the free teaser; only client-fetch when missing.
    if (initialPreview) return;
    let alive = true;
    setLoading(true);
    void fetchRadarPreview(capped)
      .then((payload) => {
        if (!alive) return;
        setPreview(payload);
        setError(null);
      })
      .catch((err) => {
        if (!alive) return;
        setPreview(null);
        setError(
          err instanceof Error
            ? err.message
            : t(variant === "pro" ? "pro_demo_error" : "landing_dotd_error"),
        );
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [capped, t, variant, initialPreview]);

  const rows = preview?.underpriced || [];
  const featured = rows[0] || null;
  const rest = rows.slice(1);
  const eyebrow =
    variant === "pro" ? t("pro_demo_eyebrow") : t("landing_dotd_eyebrow");
  const title =
    variant === "pro" ? t("pro_demo_title") : t("landing_dotd_title");
  const lede =
    variant === "pro" ? t("pro_demo_lede") : t("landing_dotd_lede");
  const empty =
    variant === "pro" ? t("pro_demo_empty") : t("landing_dotd_empty");
  const loadingLabel =
    variant === "pro" ? t("pro_demo_loading") : t("landing_dotd_loading");
  const ctaHref = variant === "pro" ? "/radar" : "/pro";
  const ctaLabel =
    variant === "pro" ? t("pro_demo_open") : t("landing_dotd_cta");
  const featuredVerdict = featured
    ? decisionOneLiner(locale, featured.side || "UNDER", featured.edge_pct)
    : null;
  const featuredBand = featured ? bandLabel(featured) : null;
  const featuredFair = featured
    ? formatSpot(featured.fair_price ?? featured.predicted_price)
    : "";
  const featuredEdge = featured ? formatChange(featured.edge_pct) : "";

  return (
    <section
      id={variant === "landing" ? "deal-of-day" : undefined}
      className={`deal-of-day ${variant === "landing" ? "landing-dotd" : "pro-demo"} ${className}`.trim()}
      aria-label={title}
    >
      <p className="explore-command-eyebrow">{eyebrow}</p>
      <h2 className={variant === "landing" ? "landing-dotd-title" : "pro-demo-title"}>
        {title}
      </h2>
      <p className="explore-lede">
        {lede}
        {variant !== "landing" && preview?.source === "demo"
          ? ` · ${t("explore_demo")}`
          : ""}
      </p>

      {loading ? (
        <DeskLoading label={loadingLabel} variant="banner" />
      ) : null}
      {error ? <p className="form-error">{error}</p> : null}
      {!loading && !error && rows.length === 0 ? (
        <p className="explore-lede">{empty}</p>
      ) : null}

      {featured ? (
        <Link
          href={`/cards/${encodeURIComponent(featured.id)}`}
          className="deal-of-day-feature radar-under"
          onClick={() =>
            trackFunnel("dotd_card_open", {
              variant,
              card_id: featured.id,
            })
          }
        >
          <div className="deal-of-day-art">
            <Image
              src={featured.image_url || "/kestrel-logo.png"}
              alt={featured.name}
              width={variant === "landing" ? 160 : 96}
              height={variant === "landing" ? 224 : 134}
            />
          </div>
          <div className="deal-of-day-copy">
            {!featuredVerdict ? (
              <div
                className="radar-side"
                title={t(sideTipKey(featured.side || "UNDER"))}
              >
                {sideLabel(locale, featured.side || "UNDER")}
              </div>
            ) : null}
            <div className="lot-name">{featured.name}</div>
            <div className="lot-meta">
              {[featured.set_name, featured.rarity].filter(Boolean).join(" · ")}
            </div>
            {featuredVerdict ? (
              <p className="decision-line">{featuredVerdict}</p>
            ) : featuredBand ? (
              <p className="lot-meta" title={t("glossary_band_tip")}>
                {t("landing_dotd_band", { band: featuredBand })}
              </p>
            ) : null}
            <div className="deal-of-day-metrics">
              <strong>{formatSpot(featured.spot ?? featured.price)}</strong>
              <span title={t("glossary_fair_tip")}>
                {t("metric_fair", { price: featuredFair })}
              </span>
              <span className="pnl-up" title={t("glossary_edge_tip")}>
                {t("metric_edge", { pct: featuredEdge })}
              </span>
            </div>
          </div>
        </Link>
      ) : null}

      {rest.length > 0 ? (
        <div className="scan-list deal-of-day-list">
          {rest.map((card) => (
            <TeaserRow key={card.id} card={card} />
          ))}
        </div>
      ) : null}

      {!loading && !error && rows.length > 0 ? (
        <Link
          href={ctaHref}
          className="btn-primary deal-of-day-cta"
          onClick={() =>
            trackFunnel("dotd_cta", { variant, target: ctaHref })
          }
        >
          {ctaLabel}
        </Link>
      ) : (
        <Link
          href={ctaHref}
          className="btn-ghost deal-of-day-cta"
          onClick={() =>
            trackFunnel("dotd_cta", { variant, target: ctaHref })
          }
        >
          {ctaLabel}
        </Link>
      )}

      {featured ? (
        <DotdShareExport
          card={featured}
          spotLabel={formatSpot(featured.spot ?? featured.price)}
          fairLabel={featuredFair}
          edgeLabel={featuredEdge}
          verdict={featuredVerdict}
        />
      ) : null}
    </section>
  );
}

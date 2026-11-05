"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { fetchRadarPreview, formatChange, formatMoney } from "@/lib/api";
import type { RadarCard, RadarPreviewResponse } from "@/lib/types";

function bandLabel(card: RadarCard): string | null {
  const lo = card.pred_lo_pct;
  const hi = card.pred_hi_pct;
  if (lo == null || hi == null) return null;
  if (!Number.isFinite(Number(lo)) || !Number.isFinite(Number(hi))) return null;
  return `${formatChange(Number(lo), 1)}…${formatChange(Number(hi), 1)}`;
}

export function DealOfTheDay({
  limit = 1,
  variant = "landing",
  className = "",
}: {
  limit?: number;
  variant?: "landing" | "pro";
  className?: string;
}) {
  const { t } = useLocale();
  const [preview, setPreview] = useState<RadarPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const capped = Math.max(1, Math.min(8, Math.floor(limit) || 1));

  useEffect(() => {
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
  }, [capped, t, variant]);

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

  return (
    <section
      className={`deal-of-day ${variant === "landing" ? "landing-dotd" : "pro-demo"} ${className}`.trim()}
      aria-label={title}
    >
      <p className="explore-command-eyebrow">{eyebrow}</p>
      <h2 className={variant === "landing" ? "landing-dotd-title" : "pro-demo-title"}>
        {title}
      </h2>
      <p className="explore-lede">
        {lede}
        {preview?.source === "demo" ? ` · ${t("explore_demo")}` : ""}
      </p>

      {loading ? <p className="explore-lede">{loadingLabel}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}
      {!loading && !error && rows.length === 0 ? (
        <p className="explore-lede">{empty}</p>
      ) : null}

      {featured ? (
        <Link
          href={`/cards/${encodeURIComponent(featured.id)}`}
          className="deal-of-day-feature radar-under"
        >
          <div className="deal-of-day-art">
            <Image
              src={featured.image_url || "/kestrel-logo.png"}
              alt={featured.name}
              width={96}
              height={134}
            />
          </div>
          <div className="deal-of-day-copy">
            <div className="radar-side">UNDER</div>
            <div className="lot-name">{featured.name}</div>
            <div className="lot-meta">
              {[featured.set_name, featured.rarity].filter(Boolean).join(" · ")}
            </div>
            <div className="deal-of-day-metrics">
              <strong>{formatMoney(featured.spot ?? featured.price)}</strong>
              <span>
                fair {formatMoney(featured.fair_price ?? featured.predicted_price)}
              </span>
              <span className="pnl-up">
                edge {formatChange(featured.edge_pct)}
              </span>
              {bandLabel(featured) ? (
                <span className="lot-meta">
                  {t("landing_dotd_band", { band: bandLabel(featured) || "" })}
                </span>
              ) : null}
            </div>
          </div>
        </Link>
      ) : null}

      {rest.length > 0 ? (
        <div className="scan-list deal-of-day-list">
          {rest.map((card) => (
            <Link
              key={card.id}
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
                <div className="radar-side">UNDER</div>
                <div className="lot-name">{card.name}</div>
                <div className="lot-meta">
                  {[card.set_name, card.rarity].filter(Boolean).join(" · ")}
                </div>
              </div>
              <div className="scan-metrics">
                <strong>{formatMoney(card.spot ?? card.price)}</strong>
                <span>
                  fair {formatMoney(card.fair_price ?? card.predicted_price)}
                </span>
                <span className="pnl-up">edge {formatChange(card.edge_pct)}</span>
              </div>
            </Link>
          ))}
        </div>
      ) : null}

      <Link href={ctaHref} className="btn-ghost deal-of-day-cta">
        {ctaLabel}
      </Link>
    </section>
  );
}

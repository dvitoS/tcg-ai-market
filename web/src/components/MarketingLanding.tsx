"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DealOfTheDay } from "@/components/DealOfTheDay";
import { HeroCardSlider } from "@/components/HeroCardSlider";
import { MarketPulse } from "@/components/MarketPulse";
import { SoftInkWash } from "@/components/SoftInkWash";
import { TrustProof } from "@/components/TrustProof";
import { useLocale } from "@/components/LocaleProvider";
import { fetchRadarPreview } from "@/lib/api";
import { trackFunnel } from "@/lib/funnel";
import type {
  MarketPulseResponse,
  RadarPreviewResponse,
} from "@/lib/types";

export function MarketingLanding({
  initialDotd = null,
  initialPulse = null,
}: {
  initialDotd?: RadarPreviewResponse | null;
  initialPulse?: MarketPulseResponse | null;
}) {
  const { t } = useLocale();
  const [dotd, setDotd] = useState<RadarPreviewResponse | null>(initialDotd);

  useEffect(() => {
    trackFunnel("landing_view", undefined, { once: true });
  }, []);

  // Hero must not stay blank when SSR preview was empty / share-safe desk cold.
  useEffect(() => {
    if ((dotd?.underpriced || []).length > 0) return;
    let alive = true;
    void fetchRadarPreview(5, { cache: "no-store" })
      .then((payload) => {
        if (!alive) return;
        if ((payload.underpriced || []).length > 0) setDotd(payload);
      })
      .catch(() => {
        /* keep SSR empty — DoTD shows its own empty copy */
      });
    return () => {
      alive = false;
    };
  }, [dotd]);

  return (
    <div className="landing">
      <section className="landing-hero" aria-label="Kestrel">
        <div className="landing-hero-plane" aria-hidden>
          <img
            src="/kestrel-hero.svg"
            alt=""
            className="landing-hero-img"
            width={1920}
            height={1080}
            decoding="async"
            fetchPriority="high"
          />
          <div className="landing-hero-veil" />
          {/* Above the veil so copper motion stays visible. */}
          <SoftInkWash />
        </div>

        <div className="landing-hero-stage">
          <div className="landing-hero-copy">
            <p className="landing-brand">Kestrel</p>
            <p className="landing-product">{t("landing_product")}</p>
            <h1 className="landing-headline">{t("landing_headline")}</h1>
            <p className="landing-lede">{t("landing_lede")}</p>
            <div className="landing-ctas">
              <a
                href="#deal-of-day"
                className="btn-primary landing-cta"
                onClick={() => trackFunnel("landing_cta_dotd")}
              >
                {t("landing_cta_market")}
              </a>
              <Link
                href="/pro"
                className="btn-ghost landing-cta"
                onClick={() => trackFunnel("landing_cta_pro")}
              >
                {t("landing_cta_pro")}
              </Link>
            </div>
          </div>
          <HeroCardSlider cards={dotd?.underpriced || []} />
        </div>
      </section>

      <div className="landing-desk">
        <MarketPulse initialPulse={initialPulse} />
        <DealOfTheDay
          limit={5}
          variant="landing"
          initialPreview={dotd}
        />
      </div>

      <section className="landing-path" aria-labelledby="landing-path-title">
        <h2 id="landing-path-title" className="landing-path-title">
          {t("landing_path_title")}
        </h2>
        <p className="landing-path-lede">{t("landing_path_lede")}</p>
        <nav className="landing-path-nav" aria-label="Kestrel desks">
          <Link href="/radar" className="landing-path-link">
            <span className="landing-path-link-title">{t("landing_path_radar")}</span>
            <span className="landing-path-link-meta">{t("landing_path_radar_meta")}</span>
          </Link>
          <Link href="/trade" className="landing-path-link">
            <span className="landing-path-link-title">{t("landing_path_trade")}</span>
            <span className="landing-path-link-meta">{t("landing_path_trade_meta")}</span>
          </Link>
          <Link href="/browse" className="landing-path-link">
            <span className="landing-path-link-title">{t("landing_path_browse")}</span>
            <span className="landing-path-link-meta">{t("landing_path_browse_meta")}</span>
          </Link>
        </nav>
      </section>

      <TrustProof />

      <section className="landing-guides" aria-labelledby="landing-guides-title">
        <h2 id="landing-guides-title" className="landing-path-title">
          {t("landing_guides_title")}
        </h2>
        <p className="landing-path-lede">{t("landing_guides_lede")}</p>
        <nav className="landing-path-nav" aria-label="Kestrel guides">
          <Link
            href="/guides/kestrel-methodology"
            className="landing-path-link"
          >
            <span className="landing-path-link-title">
              {t("landing_guides_method")}
            </span>
          </Link>
          <Link
            href="/guides/pokemon-tcg-fair-value"
            className="landing-path-link"
          >
            <span className="landing-path-link-title">
              {t("landing_guides_fair")}
            </span>
          </Link>
          <Link href="/guides/should-i-grade" className="landing-path-link">
            <span className="landing-path-link-title">
              {t("landing_guides_grade")}
            </span>
          </Link>
          <Link href="/guides/trade-fairness" className="landing-path-link">
            <span className="landing-path-link-title">
              {t("landing_guides_trade")}
            </span>
          </Link>
        </nav>
      </section>
    </div>
  );
}

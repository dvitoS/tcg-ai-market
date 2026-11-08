"use client";

import Link from "next/link";

import { DealOfTheDay } from "@/components/DealOfTheDay";
import { HeroCardSlider } from "@/components/HeroCardSlider";
import { LandingSealedStrip } from "@/components/LandingSealedStrip";
import { MarketPulse } from "@/components/MarketPulse";
import { SoftInkWash } from "@/components/SoftInkWash";
import { useLocale } from "@/components/LocaleProvider";
import type {
  MarketPulseResponse,
  RadarPreviewResponse,
  SealedQuoteResponse,
} from "@/lib/types";

export function MarketingLanding({
  initialDotd = null,
  initialPulse = null,
  initialSealed = null,
}: {
  initialDotd?: RadarPreviewResponse | null;
  initialPulse?: MarketPulseResponse | null;
  initialSealed?: SealedQuoteResponse | null;
}) {
  const { t } = useLocale();

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
              <a href="#deal-of-day" className="btn-primary landing-cta">
                {t("landing_cta_market")}
              </a>
              <Link href="/pro" className="btn-ghost landing-cta">
                {t("landing_cta_pro")}
              </Link>
            </div>
          </div>
          <HeroCardSlider cards={initialDotd?.underpriced || []} />
        </div>
      </section>

      <MarketPulse initialPulse={initialPulse} />

      <DealOfTheDay
        limit={5}
        variant="landing"
        initialPreview={initialDotd}
      />

      <LandingSealedStrip initialSealed={initialSealed} />

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

      <section className="landing-guides" aria-labelledby="landing-guides-title">
        <h2 id="landing-guides-title" className="landing-path-title">
          {t("landing_guides_title")}
        </h2>
        <p className="landing-path-lede">{t("landing_guides_lede")}</p>
        <nav className="landing-path-nav" aria-label="Kestrel guides">
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

      <section className="landing-follow" aria-labelledby="landing-follow-title">
        <h2 id="landing-follow-title" className="landing-follow-title">
          {t("landing_follow_title")}
        </h2>
        <p className="landing-follow-lede">{t("landing_follow_lede")}</p>
        <Link href="/trade" className="landing-follow-link">
          {t("landing_follow_link")}
        </Link>
      </section>
    </div>
  );
}

"use client";

import Link from "next/link";

import { useLocale } from "@/components/LocaleProvider";

export function MarketingLanding() {
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
          />
          <div className="landing-hero-veil" />
        </div>

        <div className="landing-hero-copy">
          <p className="landing-brand">Kestrel</p>
          <h1 className="landing-headline">{t("landing_headline")}</h1>
          <p className="landing-lede">{t("landing_lede")}</p>
          <div className="landing-ctas">
            <Link href="/browse" className="btn-primary landing-cta">
              {t("landing_cta_market")}
            </Link>
            <Link href="/pro" className="btn-ghost landing-cta">
              {t("landing_cta_pro")}
            </Link>
          </div>
        </div>
      </section>

      <section className="landing-follow" aria-labelledby="landing-follow-title">
        <h2 id="landing-follow-title" className="landing-follow-title">
          {t("landing_follow_title")}
        </h2>
        <p className="landing-follow-lede">{t("landing_follow_lede")}</p>
        <Link href="/browse#signals" className="landing-follow-link">
          {t("landing_follow_link")}
        </Link>
      </section>
    </div>
  );
}

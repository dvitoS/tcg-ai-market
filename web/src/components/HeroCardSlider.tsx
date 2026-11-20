"use client";

import Link from "next/link";

import { HoloCardArt } from "@/components/HoloCardArt";
import { useCurrency } from "@/components/CurrencyProvider";
import { useLocale } from "@/components/LocaleProvider";
import { resolveCardImageUrl, tcgdexImageUrlLow } from "@/lib/cardImage";
import { resolveDeskNumbers } from "@/lib/deskNumbers";
import { resolveFoilMode } from "@/lib/foilMode";
import type { RadarCard } from "@/lib/types";

/** Landing hero: one card, two prices, one call (T1.3). */
export function HeroCardSlider({ cards }: { cards: RadarCard[] }) {
  const { t } = useLocale();
  const { formatSpot } = useCurrency();
  const active = cards.filter((c) => c?.id)[0];
  if (!active) return null;

  const desk = resolveDeskNumbers({
    spot: active.spot,
    price: active.price,
    fair_price: active.fair_price,
    predicted_price: active.predicted_price,
    side: active.side,
  });
  const spot = formatSpot(desk.asking);
  const fair = formatSpot(desk.good);
  const foil = resolveFoilMode(active.finishes, active.rarity, active.name);

  return (
    <aside
      className="landing-hero-slider"
      aria-label={t("landing_hero_slider_aria")}
    >
      <div className="landing-hero-slider-stage">
        <Link
          href={`/cards/${encodeURIComponent(active.id)}`}
          className="landing-hero-slide is-active"
        >
          <HoloCardArt
            key={`${active.id}-${foil || "none"}`}
            cardId={active.id}
            name={active.name}
            image={
              tcgdexImageUrlLow(active.id) ||
              resolveCardImageUrl(active.id, active.image_url)
            }
            foil={foil}
            priority
            width={280}
            height={392}
            sizes="280px"
            fillFrame
            className="landing-hero-slide-art"
          />
        </Link>
      </div>

      <div className="landing-hero-slide-meta">
        <p className="landing-hero-slide-eyebrow">
          {t("landing_hero_slide_under")}
        </p>
        <p className="landing-hero-slide-name">{active.name}</p>
        {active.set_name ? (
          <p className="landing-hero-slide-set">{active.set_name}</p>
        ) : null}
        <p className="landing-hero-slide-prices">
          <span>{t("metric_spot", { price: spot })}</span>
          <span>{t("metric_fair", { price: fair })}</span>
        </p>
        <p className="landing-hero-slide-call">{t("landing_hero_slide_call")}</p>
      </div>
    </aside>
  );
}

"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useCurrency } from "@/components/CurrencyProvider";
import { useLocale } from "@/components/LocaleProvider";
import { formatChange } from "@/lib/api";
import type { RadarCard } from "@/lib/types";

const INTERVAL_MS = 4500;

export function HeroCardSlider({ cards }: { cards: RadarCard[] }) {
  const { t } = useLocale();
  const { formatSpot } = useCurrency();
  const slides = cards.filter((c) => c?.id).slice(0, 5);
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (slides.length <= 1 || paused) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;
    const id = window.setInterval(() => {
      setIndex((i) => (i + 1) % slides.length);
    }, INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [slides.length, paused]);

  if (!slides.length) return null;

  const active = slides[Math.min(index, slides.length - 1)];
  const edge = formatChange(active.edge_pct);
  const spot = formatSpot(active.spot ?? active.price);

  return (
    <aside
      className="landing-hero-slider"
      aria-label={t("landing_hero_slider_aria")}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
          setPaused(false);
        }
      }}
    >
      <div className="landing-hero-slider-stage">
        {slides.map((card, i) => {
          const isActive = i === index;
          return (
            <Link
              key={card.id}
              href={`/cards/${encodeURIComponent(card.id)}`}
              className={`landing-hero-slide${isActive ? " is-active" : ""}`}
              tabIndex={isActive ? 0 : -1}
              aria-hidden={!isActive}
            >
              <span className="landing-hero-slide-frame">
                <Image
                  src={card.image_url || "/kestrel-logo.png"}
                  alt=""
                  width={280}
                  height={392}
                  className="landing-hero-slide-img"
                  priority={i === 0}
                />
              </span>
            </Link>
          );
        })}
      </div>

      <div className="landing-hero-slide-meta">
        <p className="landing-hero-slide-eyebrow">{t("landing_hero_slide_under")}</p>
        <p className="landing-hero-slide-name">{active.name}</p>
        <p className="landing-hero-slide-set">
          {[active.set_name, spot].filter(Boolean).join(" · ")}
        </p>
        {active.edge_pct != null ? (
          <p className="landing-hero-slide-edge">
            {t("landing_hero_slide_edge", { pct: edge })}
          </p>
        ) : null}
      </div>

      {slides.length > 1 ? (
        <div className="landing-hero-slide-dots" role="tablist" aria-label={t("landing_hero_slider_aria")}>
          {slides.map((card, i) => (
            <button
              key={`dot-${card.id}`}
              type="button"
              role="tab"
              aria-selected={i === index}
              aria-label={card.name}
              className={`landing-hero-slide-dot${i === index ? " is-active" : ""}`}
              onClick={() => setIndex(i)}
            />
          ))}
        </div>
      ) : null}
    </aside>
  );
}

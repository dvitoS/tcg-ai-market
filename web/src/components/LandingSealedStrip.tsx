"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useCurrency } from "@/components/CurrencyProvider";
import { useLocale } from "@/components/LocaleProvider";
import { fetchSealedQuote } from "@/lib/api";
import type { SealedQuoteItem, SealedQuoteResponse } from "@/lib/types";

const INTERVAL_MS = 4800;

export function LandingSealedStrip({
  initialSealed = null,
}: {
  initialSealed?: SealedQuoteResponse | null;
}) {
  const { t } = useLocale();
  const { formatSpot } = useCurrency();
  const [sealed, setSealed] = useState<SealedQuoteResponse | null>(initialSealed);
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (initialSealed) return;
    let alive = true;
    void fetchSealedQuote({ limit: 5 })
      .then((payload) => {
        if (alive) setSealed(payload);
      })
      .catch(() => {
        if (alive) setSealed(null);
      });
    return () => {
      alive = false;
    };
  }, [initialSealed]);

  const slides = (sealed?.items || []).filter((item) => item?.card_id).slice(0, 5);

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
  const spot = formatSpot(active.spot_usd);

  return (
    <section className="landing-sealed" aria-labelledby="landing-sealed-title">
      <div className="landing-sealed-stage">
        <div className="landing-sealed-copy-block">
          <h2 id="landing-sealed-title" className="landing-pulse-title">
            {t("landing_sealed_title")}
          </h2>
          <p className="landing-path-lede">{t("landing_sealed_lede")}</p>
          <p className="landing-pulse-foot">
            <Link href="/sealed">{t("landing_sealed_cta")}</Link>
          </p>
        </div>

        <aside
          className="landing-sealed-slider"
          aria-label={t("landing_sealed_slider_aria")}
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
          onFocusCapture={() => setPaused(true)}
          onBlurCapture={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
              setPaused(false);
            }
          }}
        >
          <div className="landing-sealed-slider-stage">
            {slides.map((item: SealedQuoteItem, i) => {
              const isActive = i === index;
              return (
                <Link
                  key={`${item.card_id}-${item.tcgplayer_id || item.name}`}
                  href="/sealed"
                  className={`landing-sealed-slide${isActive ? " is-active" : ""}`}
                  tabIndex={isActive ? 0 : -1}
                  aria-hidden={!isActive}
                >
                  <span className="landing-sealed-slide-frame">
                    <Image
                      src={item.image_url || "/kestrel-logo.png"}
                      alt=""
                      width={280}
                      height={280}
                      className="landing-sealed-slide-img"
                      priority={i === 0}
                    />
                  </span>
                </Link>
              );
            })}
          </div>

          <div className="landing-sealed-slide-meta">
            <p className="landing-sealed-slide-eyebrow">
              {t("landing_sealed_slide_label")}
            </p>
            <p className="landing-sealed-slide-name">{active.name}</p>
            <p className="landing-sealed-slide-set">
              {[active.set_name, spot].filter(Boolean).join(" · ")}
            </p>
          </div>

          {slides.length > 1 ? (
            <div
              className="landing-hero-slide-dots"
              role="tablist"
              aria-label={t("landing_sealed_slider_aria")}
            >
              {slides.map((item, i) => (
                <button
                  key={`dot-${item.card_id}-${item.tcgplayer_id || item.name}`}
                  type="button"
                  role="tab"
                  aria-selected={i === index}
                  aria-label={item.name}
                  className={`landing-hero-slide-dot${i === index ? " is-active" : ""}`}
                  onClick={() => setIndex(i)}
                />
              ))}
            </div>
          ) : null}
        </aside>
      </div>
    </section>
  );
}

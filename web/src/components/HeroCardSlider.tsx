"use client";

import Image from "next/image";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";

import { useCurrency } from "@/components/CurrencyProvider";
import { useLocale } from "@/components/LocaleProvider";
import { formatChange } from "@/lib/api";
import type { RadarCard } from "@/lib/types";

const INTERVAL_MS = 4500;
const TILT_MAX = 12;

export function HeroCardSlider({ cards }: { cards: RadarCard[] }) {
  const { t } = useLocale();
  const { formatSpot } = useCurrency();
  const slides = cards.filter((c) => c?.id).slice(0, 5);
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const frameRef = useRef<HTMLSpanElement | null>(null);
  const reduceRef = useRef(false);

  useEffect(() => {
    reduceRef.current = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
  }, []);

  useEffect(() => {
    if (slides.length <= 1 || paused) return;
    if (reduceRef.current) return;
    const id = window.setInterval(() => {
      setIndex((i) => (i + 1) % slides.length);
    }, INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [slides.length, paused]);

  const resetTilt = useCallback(() => {
    const frame = frameRef.current;
    if (!frame) return;
    frame.style.removeProperty("--rx");
    frame.style.removeProperty("--ry");
    frame.style.removeProperty("--gx");
    frame.style.removeProperty("--gy");
    frame.style.removeProperty("--go");
    frame.classList.remove("is-tilting");
  }, []);

  const onPointerMove = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    if (reduceRef.current) return;
    const frame = frameRef.current;
    if (!frame) return;
    const rect = frame.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    const ry = (x - 0.5) * 2 * TILT_MAX;
    const rx = (0.5 - y) * 2 * TILT_MAX;
    frame.classList.add("is-tilting");
    frame.style.setProperty("--ry", `${ry.toFixed(2)}deg`);
    frame.style.setProperty("--rx", `${rx.toFixed(2)}deg`);
    frame.style.setProperty("--gx", `${(x * 100).toFixed(1)}%`);
    frame.style.setProperty("--gy", `${(y * 100).toFixed(1)}%`);
    frame.style.setProperty("--go", "1");
  }, []);

  if (!slides.length) return null;

  const active = slides[Math.min(index, slides.length - 1)];
  const edge = formatChange(active.edge_pct);
  const spot = formatSpot(active.spot ?? active.price);

  return (
    <aside
      className="landing-hero-slider"
      aria-label={t("landing_hero_slider_aria")}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => {
        setPaused(false);
        resetTilt();
      }}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
          setPaused(false);
          resetTilt();
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
              onPointerMove={isActive ? onPointerMove : undefined}
              onPointerLeave={isActive ? resetTilt : undefined}
              onPointerCancel={isActive ? resetTilt : undefined}
            >
              <span
                ref={isActive ? frameRef : undefined}
                className="landing-hero-slide-frame"
              >
                <Image
                  src={card.image_url || "/kestrel-logo.png"}
                  alt=""
                  width={280}
                  height={392}
                  className="landing-hero-slide-img"
                  priority={i === 0}
                />
                <span className="landing-hero-slide-glare" aria-hidden="true" />
                <span className="landing-hero-slide-sheen" aria-hidden="true" />
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
        <div
          className="landing-hero-slide-dots"
          role="tablist"
          aria-label={t("landing_hero_slider_aria")}
        >
          {slides.map((card, i) => (
            <button
              key={`dot-${card.id}`}
              type="button"
              role="tab"
              aria-selected={i === index}
              aria-label={card.name}
              className={`landing-hero-slide-dot${i === index ? " is-active" : ""}`}
              onClick={() => {
                resetTilt();
                setIndex(i);
              }}
            />
          ))}
        </div>
      ) : null}
    </aside>
  );
}

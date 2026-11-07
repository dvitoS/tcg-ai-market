"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useCurrency } from "@/components/CurrencyProvider";
import { useLocale } from "@/components/LocaleProvider";
import { fetchMarketPulse, formatChange } from "@/lib/api";
import type { MessageKey } from "@/lib/i18n/messages";
import type { MarketMover, MarketPulseResponse } from "@/lib/types";

function pulseStoryKey(pulse: MarketPulseResponse): {
  key: MessageKey;
  params?: Record<string, string | number>;
} {
  const under = pulse.sure_under;
  const over = pulse.sure_over;
  const share = pulse.rising_share_pct;
  const median = pulse.median_change_7d_pct;

  if (under > 0 && under >= over * 1.4) {
    return { key: "landing_pulse_story_under", params: { n: under } };
  }
  if (over > 0 && over >= under * 1.4) {
    return { key: "landing_pulse_story_over", params: { n: over } };
  }
  if (share != null && share >= 58) {
    return {
      key: "landing_pulse_story_rising",
      params: { pct: formatChange(median, 1) },
    };
  }
  if (share != null && share <= 42) {
    return {
      key: "landing_pulse_story_falling",
      params: { pct: formatChange(median, 1) },
    };
  }
  return { key: "landing_pulse_story_mixed", params: { under, over } };
}

function MoverTile({
  mover,
  tone,
  index,
}: {
  mover: MarketMover;
  tone: "up" | "down";
  index: number;
}) {
  const { formatSpot } = useCurrency();
  const chg = mover.price_change_7d_pct;
  return (
    <Link
      href={`/cards/${encodeURIComponent(mover.id)}`}
      className={`landing-mover is-${tone}`}
      style={{ animationDelay: `${0.08 + index * 0.06}s` }}
    >
      <span className="landing-mover-art">
        <Image
          src={mover.image_url || "/kestrel-logo.png"}
          alt=""
          width={72}
          height={100}
        />
      </span>
      <span className="landing-mover-copy">
        <span className="landing-mover-name">{mover.name}</span>
        <span className="landing-mover-meta">
          {[mover.set_name, formatSpot(mover.price)].filter(Boolean).join(" · ")}
        </span>
      </span>
      <span className={`landing-mover-chg is-${tone}`} aria-label={formatChange(chg)}>
        <span className="landing-mover-chg-arrow" aria-hidden="true">
          {tone === "up" ? "▲" : "▼"}
        </span>
        <span className="landing-mover-chg-num">{formatChange(chg)}</span>
      </span>
    </Link>
  );
}

export function MarketPulse({
  initialPulse = null,
}: {
  initialPulse?: MarketPulseResponse | null;
}) {
  const { t } = useLocale();
  const [pulse, setPulse] = useState<MarketPulseResponse | null>(initialPulse);

  useEffect(() => {
    if (initialPulse) return;
    let alive = true;
    void fetchMarketPulse(5)
      .then((payload) => {
        if (alive) setPulse(payload);
      })
      .catch(() => {
        if (alive) setPulse(null);
      });
    return () => {
      alive = false;
    };
  }, [initialPulse]);

  if (!pulse || pulse.source === "empty" || pulse.board_total <= 0) {
    return null;
  }

  const story = pulseStoryKey(pulse);
  const hasMovers = pulse.risers.length > 0 || pulse.fallers.length > 0;
  const medianTone =
    (pulse.median_change_7d_pct ?? 0) >= 0 ? "is-buy" : "is-sell";

  return (
    <section className="landing-pulse" aria-labelledby="landing-pulse-title">
      <div className="landing-pulse-head">
        <p className="landing-pulse-eyebrow">{t("landing_pulse_eyebrow")}</p>
        <h2 id="landing-pulse-title" className="landing-pulse-title">
          {t("landing_pulse_title")}
        </h2>
        <p className="landing-pulse-story">{t(story.key, story.params)}</p>
      </div>

      <dl className="landing-pulse-stats">
        <div>
          <dt>{t("landing_pulse_sure_under")}</dt>
          <dd className="is-buy landing-pulse-stat-num">{pulse.sure_under}</dd>
        </div>
        <div>
          <dt>{t("landing_pulse_sure_over")}</dt>
          <dd className="is-sell landing-pulse-stat-num">{pulse.sure_over}</dd>
        </div>
        <div>
          <dt>{t("landing_pulse_median_7d")}</dt>
          <dd className={`${medianTone} landing-pulse-stat-num`}>
            {formatChange(pulse.median_change_7d_pct)}
          </dd>
        </div>
        <div>
          <dt>{t("landing_pulse_breadth")}</dt>
          <dd className="landing-pulse-stat-num">
            <span className="is-buy">{pulse.rising_n}</span>
            <span className="landing-pulse-sep">↑</span>
            <span className="landing-pulse-flat">{pulse.flat_n}</span>
            <span className="landing-pulse-sep">↓</span>
            <span className="is-sell">{pulse.falling_n}</span>
          </dd>
        </div>
      </dl>

      {hasMovers ? (
        <div className="landing-trends">
          <div className="landing-trends-col">
            <h3 className="landing-trends-title is-up">
              {t("landing_trends_rising")}
            </h3>
            <div className="landing-movers">
              {pulse.risers.map((m, i) => (
                <MoverTile key={`up-${m.id}`} mover={m} tone="up" index={i} />
              ))}
            </div>
          </div>
          <div className="landing-trends-col">
            <h3 className="landing-trends-title is-down">
              {t("landing_trends_falling")}
            </h3>
            <div className="landing-movers">
              {pulse.fallers.map((m, i) => (
                <MoverTile key={`dn-${m.id}`} mover={m} tone="down" index={i} />
              ))}
            </div>
          </div>
        </div>
      ) : null}

      <p className="landing-pulse-foot">
        <Link href="/browse">{t("landing_pulse_browse")}</Link>
        <span aria-hidden="true"> · </span>
        <Link href="/radar">{t("landing_pulse_radar")}</Link>
      </p>
    </section>
  );
}

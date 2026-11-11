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
import { fetchMarketPulse, formatChange } from "@/lib/api";
import { onCardImageError, resolveCardImageUrl } from "@/lib/cardImage";
import type { MessageKey } from "@/lib/i18n/messages";
import type { MarketMover, MarketPulseResponse } from "@/lib/types";

const TILT_MAX = 14;

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

function MoverCard({
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
  const frameRef = useRef<HTMLSpanElement | null>(null);
  const reduceRef = useRef(false);

  useEffect(() => {
    reduceRef.current = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
  }, []);

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

  const onPointerMove = useCallback((event: ReactPointerEvent<HTMLAnchorElement>) => {
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

  return (
    <Link
      href={`/cards/${encodeURIComponent(mover.id)}`}
      className={`landing-mover-card is-${tone}`}
      style={{ animationDelay: `${0.05 + index * 0.09}s` }}
      onPointerMove={onPointerMove}
      onPointerLeave={resetTilt}
      onPointerCancel={resetTilt}
    >
      <span className="landing-mover-card-stage">
        <span ref={frameRef} className="landing-mover-card-frame">
          <Image
            src={resolveCardImageUrl(mover.id, mover.image_url)}
            alt=""
            width={160}
            height={224}
            className="landing-mover-card-img"
            onError={(event) => onCardImageError(event, mover.id)}
          />
          <span className="landing-mover-card-glare" aria-hidden="true" />
          <span className="landing-mover-card-sheen" aria-hidden="true" />
        </span>
      </span>
      <span className="landing-mover-card-copy">
        <span className="landing-mover-card-name">{mover.name}</span>
        {mover.set_name ? (
          <span className="landing-mover-card-set">{mover.set_name}</span>
        ) : null}
        <span className="landing-mover-card-prices">
          <span className="landing-mover-card-spot">{formatSpot(mover.price)}</span>
          <span className={`landing-mover-card-chg is-${tone}`}>
            <span aria-hidden="true">{tone === "up" ? "▲" : "▼"}</span>
            {formatChange(chg)}
          </span>
        </span>
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

  const [openTip, setOpenTip] = useState<string | null>(null);

  if (!pulse || pulse.source === "empty" || pulse.board_total <= 0) {
    return null;
  }

  const story = pulseStoryKey(pulse);
  const hasMovers = pulse.risers.length > 0 || pulse.fallers.length > 0;
  const medianTone =
    (pulse.median_change_7d_pct ?? 0) >= 0 ? "is-buy" : "is-sell";
  const stats: Array<{
    id: string;
    label: MessageKey;
    tip: MessageKey;
  }> = [
    {
      id: "under",
      label: "landing_pulse_sure_under",
      tip: "landing_pulse_sure_under_tip",
    },
    {
      id: "over",
      label: "landing_pulse_sure_over",
      tip: "landing_pulse_sure_over_tip",
    },
    {
      id: "median",
      label: "landing_pulse_median_7d",
      tip: "landing_pulse_median_7d_tip",
    },
    {
      id: "breadth",
      label: "landing_pulse_breadth",
      tip: "landing_pulse_breadth_tip",
    },
  ];

  return (
    <section className="landing-pulse" aria-labelledby="landing-pulse-title">
      <div className="landing-pulse-head">
        <p className="landing-pulse-eyebrow">{t("landing_pulse_eyebrow")}</p>
        <h2 id="landing-pulse-title" className="landing-pulse-title">
          {t("landing_pulse_title")}
        </h2>
        <p className="landing-pulse-story">{t(story.key, story.params)}</p>
      </div>

      {hasMovers ? (
        <div className="landing-trends">
          <div className="landing-trends-col">
            <h3 className="landing-trends-title is-up">
              {t("landing_trends_rising")}
            </h3>
            <div className="landing-mover-rail">
              {pulse.risers.slice(0, 4).map((m, i) => (
                <MoverCard key={`up-${m.id}`} mover={m} tone="up" index={i} />
              ))}
            </div>
          </div>
          <div className="landing-trends-col">
            <h3 className="landing-trends-title is-down">
              {t("landing_trends_falling")}
            </h3>
            <div className="landing-mover-rail">
              {pulse.fallers.slice(0, 4).map((m, i) => (
                <MoverCard key={`dn-${m.id}`} mover={m} tone="down" index={i} />
              ))}
            </div>
          </div>
        </div>
      ) : null}

      <dl className="landing-pulse-stats">
        {stats.map((stat) => {
          const open = openTip === stat.id;
          return (
            <div
              key={stat.id}
              className={`landing-pulse-stat${open ? " is-open" : ""}`}
              title={t(stat.tip)}
            >
              <dt>
                <button
                  type="button"
                  className="landing-pulse-stat-btn"
                  aria-expanded={open}
                  aria-controls={`pulse-tip-${stat.id}`}
                  onClick={() =>
                    setOpenTip((cur) => (cur === stat.id ? null : stat.id))
                  }
                >
                  <span>{t(stat.label)}</span>
                  <span className="landing-pulse-stat-q" aria-hidden="true">
                    ?
                  </span>
                </button>
              </dt>
              {stat.id === "under" ? (
                <dd className="is-buy landing-pulse-stat-num">
                  {pulse.sure_under}
                </dd>
              ) : null}
              {stat.id === "over" ? (
                <dd className="is-sell landing-pulse-stat-num">
                  {pulse.sure_over}
                </dd>
              ) : null}
              {stat.id === "median" ? (
                <dd className={`${medianTone} landing-pulse-stat-num`}>
                  {formatChange(pulse.median_change_7d_pct)}
                </dd>
              ) : null}
              {stat.id === "breadth" ? (
                <dd className="landing-pulse-stat-num landing-pulse-breadth">
                  <span className="is-buy landing-pulse-breadth-main">
                    {pulse.rising_n}
                  </span>
                  <span className="landing-pulse-breadth-sides">
                    <span className="landing-pulse-sep" aria-hidden="true">
                      ↑
                    </span>
                    <span className="landing-pulse-flat">{pulse.flat_n}</span>
                    <span className="landing-pulse-sep" aria-hidden="true">
                      ↓
                    </span>
                    <span className="is-sell">{pulse.falling_n}</span>
                  </span>
                </dd>
              ) : null}
              <p
                id={`pulse-tip-${stat.id}`}
                className="landing-pulse-tip-text"
                hidden={!open}
              >
                {t(stat.tip)}
              </p>
            </div>
          );
        })}
      </dl>

      <p className="landing-pulse-foot">
        <Link href="/browse">{t("landing_pulse_browse")}</Link>
        <span aria-hidden="true"> · </span>
        <Link href="/radar">{t("landing_pulse_radar")}</Link>
      </p>
    </section>
  );
}

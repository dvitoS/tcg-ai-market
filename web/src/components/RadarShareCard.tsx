"use client";

import { forwardRef } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { resolveCardImageUrl } from "@/lib/cardImage";
import { formatRadarShareFilters, type RadarShareFilters } from "@/lib/radarShare";
import type { RadarCard } from "@/lib/types";

export const RadarShareCard = forwardRef<
  HTMLDivElement,
  {
    filters: RadarShareFilters;
    underTotal: number;
    overTotal: number;
    topUnder: RadarCard | null;
    spotLabel: string;
    fairLabel: string;
    edgeLabel: string;
    shareUrl?: string | null;
  }
>(function RadarShareCard(
  {
    filters,
    underTotal,
    overTotal,
    topUnder,
    spotLabel,
    fairLabel,
    edgeLabel,
    shareUrl,
  },
  ref,
) {
  const { t } = useLocale();
  const chips = formatRadarShareFilters(filters);
  const meta = topUnder
    ? [topUnder.set_name, topUnder.rarity].filter(Boolean).join(" · ")
    : null;

  return (
    <div ref={ref} className="dotd-share-card radar-share-card" data-radar-report="1">
      <header className="trade-share-card-brand">
        <img
          src="/kestrel-logo.png"
          alt=""
          width={36}
          height={36}
          className="trade-share-card-mark"
        />
        <div>
          <p className="trade-share-card-kestrel">Kestrel</p>
          <p className="trade-share-card-tag">{t("radar_export_tag")}</p>
        </div>
      </header>

      <p className="dotd-share-verdict">
        {t("radar_share_board", { under: underTotal, over: overTotal })}
      </p>
      {chips.length ? (
        <p className="lot-meta">
          {t("radar_share_filters")}: {chips.join(" · ")}
        </p>
      ) : null}

      {topUnder ? (
        <div className="dotd-share-body">
          <div className="dotd-share-art">
            <img
              src={resolveCardImageUrl(topUnder.id, topUnder.image_url)}
              alt=""
              width={140}
              height={196}
            />
          </div>
          <div className="dotd-share-copy">
            <p className="dotd-share-side">{t("glossary_under")}</p>
            <h2 className="dotd-share-name">{topUnder.name}</h2>
            {meta ? <p className="lot-meta">{meta}</p> : null}
            <div className="dotd-share-metrics">
              <strong>{spotLabel}</strong>
              <span>{t("metric_fair", { price: fairLabel })}</span>
              <span className="pnl-up">
                {t("metric_edge", { pct: edgeLabel })}
              </span>
            </div>
          </div>
        </div>
      ) : null}

      <p className="dotd-share-note">{t("radar_export_note")}</p>

      <footer className="trade-share-card-foot">
        <div className="trade-share-card-foot-copy">
          <span>{t("radar_export_watermark")}</span>
          <span className="trade-share-card-pro">{t("radar_export_cta")}</span>
        </div>
        {shareUrl ? (
          <span className="trade-share-card-url">{shareUrl}</span>
        ) : null}
      </footer>
    </div>
  );
});

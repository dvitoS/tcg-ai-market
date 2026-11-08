"use client";

import { forwardRef } from "react";

import { useLocale } from "@/components/LocaleProvider";
import type { RadarCard } from "@/lib/types";

export const DotdShareCard = forwardRef<
  HTMLDivElement,
  {
    card: RadarCard;
    spotLabel: string;
    fairLabel: string;
    edgeLabel: string;
    verdict: string | null;
    shareUrl?: string | null;
  }
>(function DotdShareCard(
  { card, spotLabel, fairLabel, edgeLabel, verdict, shareUrl },
  ref,
) {
  const { t } = useLocale();
  const meta = [card.set_name, card.rarity].filter(Boolean).join(" · ");
  return (
    <div ref={ref} className="dotd-share-card" data-dotd-report="1">
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
          <p className="trade-share-card-tag">{t("dotd_export_tag")}</p>
        </div>
      </header>

      <div className="dotd-share-body">
        <div className="dotd-share-art">
          <img
            src={card.image_url || "/kestrel-logo.png"}
            alt=""
            width={140}
            height={196}
          />
        </div>
        <div className="dotd-share-copy">
          <p className="dotd-share-side">{t("glossary_under")}</p>
          <h2 className="dotd-share-name">{card.name}</h2>
          {meta ? <p className="lot-meta">{meta}</p> : null}
          {verdict ? <p className="dotd-share-verdict">{verdict}</p> : null}
          <div className="dotd-share-metrics">
            <strong>{spotLabel}</strong>
            <span>{t("metric_fair", { price: fairLabel })}</span>
            <span className="pnl-up">{t("metric_edge", { pct: edgeLabel })}</span>
          </div>
        </div>
      </div>

      <p className="dotd-share-note">{t("dotd_export_note")}</p>

      <footer className="trade-share-card-foot">
        <div className="trade-share-card-foot-copy">
          <span>{t("dotd_export_watermark")}</span>
          <span className="trade-share-card-pro">{t("dotd_export_cta")}</span>
        </div>
        {shareUrl ? <span className="trade-share-card-url">{shareUrl}</span> : null}
      </footer>
    </div>
  );
});

"use client";

import Image from "next/image";
import Link from "next/link";

import { useLocale } from "@/components/LocaleProvider";
import { formatChange, formatMoney } from "@/lib/api";
import { signalLabel } from "@/lib/i18n/messages";
import type { CatalogCard } from "@/lib/types";

function changeClass(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "flat";
  if (value > 0.05) return "up";
  if (value < -0.05) return "down";
  return "flat";
}

function signalTone(signal?: string | null): string {
  const key = (signal || "").toUpperCase();
  if (key === "BUY") return "is-buy";
  if (key === "SELL") return "is-sell";
  if (key === "HOLD") return "is-hold";
  return "";
}

export function ExploreCard({
  card,
  showSignal = false,
}: {
  card: CatalogCard;
  showSignal?: boolean;
}) {
  const { locale } = useLocale();
  const meta = [card.set_name, card.rarity].filter(Boolean).join(" · ");
  const image = card.image_url || "/kestrel-logo.png";
  const tone = showSignal ? signalTone(card.signal) : "";
  const delta = changeClass(card.expected_change_pct);

  return (
    <Link
      href={`/cards/${encodeURIComponent(card.id)}`}
      className={`explore-card ${tone}`}
    >
      <div className="explore-card-art">
        <Image
          src={image}
          alt={card.name}
          width={245}
          height={342}
          className="explore-card-img"
          sizes="(max-width: 640px) 45vw, (max-width: 1024px) 22vw, 180px"
        />
        <div className="explore-card-readout" aria-hidden={false}>
          <span className="explore-card-price">{formatMoney(card.price)}</span>
          <span className={`explore-card-change ${delta}`}>
            {formatChange(card.expected_change_pct)}
            {showSignal && card.signal
              ? ` · ${signalLabel(locale, card.signal)}`
              : ""}
          </span>
        </div>
      </div>
      <div className="explore-card-copy">
        <div className="explore-card-name">{card.name}</div>
        {meta ? <div className="explore-card-meta">{meta}</div> : null}
      </div>
    </Link>
  );
}

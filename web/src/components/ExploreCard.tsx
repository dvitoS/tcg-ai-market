"use client";

import Image from "next/image";
import Link from "next/link";

import { useCurrency } from "@/components/CurrencyProvider";
import { useLocale } from "@/components/LocaleProvider";
import { formatChange } from "@/lib/api";
import { signalLabel, translate } from "@/lib/i18n/messages";
import type { CatalogCard } from "@/lib/types";

function changeClass(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "flat";
  if (value > 0.05) return "up";
  if (value < -0.05) return "down";
  return "flat";
}

function changeArrow(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "";
  if (value > 0.05) return "↑";
  if (value < -0.05) return "↓";
  return "";
}

function signalTone(signal?: string | null): string {
  const key = (signal || "").toUpperCase();
  if (key === "BUY") return "is-buy";
  if (key === "SELL") return "is-sell";
  if (key === "HOLD") return "is-hold";
  return "";
}

function MoveRow({
  label,
  value,
}: {
  label: string;
  value?: number | null;
}) {
  const arrow = changeArrow(value);
  return (
    <span className={`explore-card-move ${changeClass(value)}`}>
      <span className="explore-card-move-label">{label}</span>
      <span className="explore-card-move-value">
        {arrow ? (
          <span className="explore-card-move-arrow" aria-hidden="true">
            {arrow}
          </span>
        ) : null}
        {formatChange(value)}
      </span>
    </span>
  );
}

export function ExploreCard({
  card,
  showSignal = false,
}: {
  card: CatalogCard;
  showSignal?: boolean;
}) {
  const { locale } = useLocale();
  const { formatSpot } = useCurrency();
  const meta = [card.set_name, card.rarity].filter(Boolean).join(" · ");
  const image = card.image_url || "/kestrel-logo.png";
  const tone = showSignal ? signalTone(card.signal) : "";
  // Prefer true 3d history; fall back to 7d history so older boards still show a past move.
  const histMove =
    card.price_change_3d_pct != null
      ? card.price_change_3d_pct
      : card.price_change_7d_pct;
  const histLabel =
    card.price_change_3d_pct != null
      ? translate(locale, "card_move_3d")
      : translate(locale, "card_move_7d");
  // Prefer stronger 30d portfolio model; fall back to board 7d AI when 30d is missing.
  const aiMove =
    card.expected_change_30d_pct != null
      ? card.expected_change_30d_pct
      : card.expected_change_pct;
  const aiLabel =
    card.expected_change_30d_pct != null
      ? translate(locale, "card_move_ai_30d")
      : translate(locale, "card_move_ai_7d");

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
          <span className="explore-card-price">{formatSpot(card.price)}</span>
          <div className="explore-card-moves">
            <MoveRow label={histLabel} value={histMove} />
            <MoveRow label={aiLabel} value={aiMove} />
          </div>
          {showSignal && card.signal ? (
            <span className="explore-card-change flat">
              {signalLabel(locale, card.signal)}
            </span>
          ) : null}
        </div>
      </div>
      <div className="explore-card-copy">
        <div className="explore-card-name">{card.name}</div>
        {meta ? <div className="explore-card-meta">{meta}</div> : null}
      </div>
    </Link>
  );
}

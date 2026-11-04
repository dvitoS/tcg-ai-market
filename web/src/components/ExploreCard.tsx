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
  const signalClass = (card.signal || "").toLowerCase();

  return (
    <Link href={`/cards/${encodeURIComponent(card.id)}`} className="explore-card">
      <div className="explore-card-art">
        <Image
          src={image}
          alt={card.name}
          width={245}
          height={342}
          className="explore-card-img"
          sizes="(max-width: 640px) 45vw, (max-width: 1024px) 22vw, 180px"
        />
      </div>
      <div className="explore-card-price">{formatMoney(card.price)}</div>
      <div className="explore-card-name">{card.name}</div>
      <div className="explore-card-meta">{meta}</div>
      <div className={`explore-card-change ${changeClass(card.expected_change_pct)}`}>
        {formatChange(card.expected_change_pct)}
      </div>
      {showSignal && card.signal ? (
        <div className={`explore-card-signal signal-${signalClass}`}>
          {signalLabel(locale, card.signal)}
        </div>
      ) : null}
    </Link>
  );
}

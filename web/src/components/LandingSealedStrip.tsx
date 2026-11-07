"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useCurrency } from "@/components/CurrencyProvider";
import { useLocale } from "@/components/LocaleProvider";
import { fetchSealedQuote } from "@/lib/api";
import type { SealedQuoteItem, SealedQuoteResponse } from "@/lib/types";

export function LandingSealedStrip({
  initialSealed = null,
}: {
  initialSealed?: SealedQuoteResponse | null;
}) {
  const { t } = useLocale();
  const { formatSpot } = useCurrency();
  const [sealed, setSealed] = useState<SealedQuoteResponse | null>(initialSealed);

  useEffect(() => {
    if (initialSealed) return;
    let alive = true;
    void fetchSealedQuote({ limit: 4 })
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

  const items = (sealed?.items || []).slice(0, 4);
  if (!items.length) return null;

  return (
    <section className="landing-sealed" aria-labelledby="landing-sealed-title">
      <div className="landing-sealed-head">
        <h2 id="landing-sealed-title" className="landing-pulse-title">
          {t("landing_sealed_title")}
        </h2>
        <p className="landing-path-lede">{t("landing_sealed_lede")}</p>
      </div>
      <div className="landing-sealed-grid">
        {items.map((item: SealedQuoteItem) => (
          <Link
            key={`${item.card_id}-${item.tcgplayer_id || item.name}`}
            href="/sealed"
            className="landing-sealed-tile"
          >
            <span className="landing-sealed-art">
              <Image
                src={item.image_url || "/kestrel-logo.png"}
                alt=""
                width={72}
                height={72}
              />
            </span>
            <span className="landing-sealed-copy">
              <span className="landing-sealed-name">{item.name}</span>
              <span className="landing-sealed-spot">
                {formatSpot(item.spot_usd)}
              </span>
            </span>
          </Link>
        ))}
      </div>
      <p className="landing-pulse-foot">
        <Link href="/sealed">{t("landing_sealed_cta")}</Link>
      </p>
    </section>
  );
}

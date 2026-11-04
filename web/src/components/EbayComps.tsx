"use client";

import { useEffect, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { fetchEbayComps, formatMoney } from "@/lib/api";
import type { EbayCompsResponse, EbayListing } from "@/lib/types";

function EbayRow({ row }: { row: EbayListing }) {
  const href = (row.url || "").trim();
  const img = (row.image || "").trim();
  return (
    <div className="ebay-row">
      <div className="ebay-thumb">
        {img.startsWith("http") ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={img} alt="" loading="lazy" referrerPolicy="no-referrer" />
        ) : null}
      </div>
      <div className="ebay-copy">
        <div className="ebay-title">{row.title || "Listing"}</div>
        <div className="ebay-meta">
          {[row.condition, row.sold_date, row.seller].filter(Boolean).join(" · ") || "—"}
        </div>
      </div>
      <div className="ebay-price">
        {row.price != null ? formatMoney(row.price, row.currency || "USD", 2) : "—"}
      </div>
      {href.startsWith("http") ? (
        <a
          className="ebay-link"
          href={href}
          target="_blank"
          rel="noopener noreferrer sponsored"
        >
          eBay ↗
        </a>
      ) : (
        <span className="ebay-link ebay-link-muted">—</span>
      )}
    </div>
  );
}

export function EbayComps({
  cardId,
  cardName,
}: {
  cardId: string;
  cardName: string;
}) {
  const { t } = useLocale();
  const [data, setData] = useState<EbayCompsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    void fetchEbayComps(cardId)
      .then((payload) => {
        if (!alive) return;
        setData(payload);
      })
      .catch((err) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "eBay comps failed");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [cardId]);

  const listings = data?.listings || [];
  const sold = data?.sold || [];
  const fallback = data?.active_fallback || [];
  const lowest = listings
    .map((r) => r.price)
    .filter((n): n is number => n != null && Number.isFinite(n));

  return (
    <section className="ebay-panel" aria-label={`${t("ebay_title")} · ${cardName}`}>
      <div className="ebay-block">
        <div className="ebay-head">
          <h2>{t("ebay_title")}</h2>
          <p>Active asks near this card.</p>
        </div>
        {loading ? <p className="empty-state">{t("ebay_loading")}</p> : null}
        {error ? <p className="banner-error">{error}</p> : null}
        {!loading && data && !data.configured ? (
          <p className="empty-state">eBay credentials are not configured on the API.</p>
        ) : null}
        {!loading && data?.listings_error ? (
          <p className="banner-error">{data.listings_error}</p>
        ) : null}
        {!loading && data?.configured && !data.listings_error && listings.length === 0 ? (
          <p className="empty-state">{t("ebay_empty")}</p>
        ) : null}
        {listings.length > 0 ? (
          <>
            {lowest.length ? (
              <p className="ebay-caption">
                From {formatMoney(Math.min(...lowest), "USD", 2)} · {listings.length} listings
              </p>
            ) : null}
            {data?.epn ? (
              <p className="ebay-caption">Links may include eBay Partner Network tracking.</p>
            ) : null}
            <div className="ebay-list">
              {listings.map((row, idx) => (
                <EbayRow key={`${row.item_id || row.url || idx}-a`} row={row} />
              ))}
            </div>
          </>
        ) : null}
      </div>

      <div className="ebay-block">
        <div className="ebay-head">
          <h2>Sold comps</h2>
          <p>Recent sold sales when Marketplace Insights is available.</p>
        </div>
        {!loading && data?.configured && sold.length === 0 ? (
          <p className="empty-state">
            {data.sold_fallback_active
              ? "Sold history unavailable — showing active asks as a soft proxy below."
              : data.sold_hint || "No sold comps for this card yet."}
          </p>
        ) : null}
        {sold.length > 0 && data?.sold_stats.n ? (
          <p className="ebay-caption">
            {data.sold_stats.n} sold ·{" "}
            {formatMoney(data.sold_stats.min, "USD", 2)} –{" "}
            {formatMoney(data.sold_stats.max, "USD", 2)}
          </p>
        ) : null}
        {sold.length > 0 ? (
          <div className="ebay-list">
            {sold.map((row, idx) => (
              <EbayRow key={`${row.item_id || row.url || idx}-s`} row={row} />
            ))}
          </div>
        ) : null}
        {!loading && data?.sold_fallback_active && fallback.length > 0 ? (
          <div className="ebay-list">
            {fallback.map((row, idx) => (
              <EbayRow key={`${row.item_id || row.url || idx}-f`} row={row} />
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}

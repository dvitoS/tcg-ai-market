"use client";

import { useEffect, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { fetchEbayComps, formatMoney } from "@/lib/api";
import type { EbayCompsResponse, EbayListing } from "@/lib/types";

function EbayRow({ row }: { row: EbayListing }) {
  const href = (row.url || "").trim();
  const img = (row.image || "").trim();
  const sold = Boolean(row.is_sold || row.sold_date);
  return (
    <div className={`ebay-row${sold ? " is-sold" : ""}`}>
      <div className="ebay-thumb">
        {img.startsWith("http") ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={img} alt="" loading="lazy" referrerPolicy="no-referrer" />
        ) : null}
      </div>
      <div className="ebay-copy">
        <div className="ebay-title">{row.title || "Listing"}</div>
        <div className="ebay-meta">
          {[row.condition, row.sold_date, row.seller].filter(Boolean).join(" · ") ||
            "—"}
        </div>
      </div>
      <div className="ebay-price">
        {row.price != null
          ? formatMoney(row.price, row.currency || "USD", 2)
          : "—"}
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
        setError(err instanceof Error ? err.message : t("ebay_unavailable"));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [cardId, t]);

  const listings = data?.listings || [];
  const sold = data?.sold || [];
  const fallback = data?.active_fallback || [];
  const stats = data?.sold_stats;
  const lowest = listings
    .map((r) => r.price)
    .filter((n): n is number => n != null && Number.isFinite(n));

  return (
    <section
      className="ebay-panel"
      aria-label={`${t("ebay_title")} · ${cardName}`}
    >
      {/* Sold first — trust signal next to the fair band. */}
      <div className="ebay-block ebay-sold-block">
        <div className="ebay-head">
          <h2>{t("ebay_sold_title")}</h2>
          <p>{t("ebay_sold_lede")}</p>
        </div>
        {loading ? <p className="empty-state">{t("ebay_loading")}</p> : null}
        {!loading &&
        data?.configured &&
        sold.length === 0 &&
        !data.sold_fallback_active ? (
          <p className="empty-state">
            {data.sold_hint || t("ebay_sold_empty")}
          </p>
        ) : null}
        {sold.length > 0 && stats?.n ? (
          <div className="ebay-cluster" aria-label={t("ebay_sold_cluster")}>
            <div className="ebay-cluster-metric">
              <span>{t("ebay_sold_median")}</span>
              <strong>
                {stats.median != null
                  ? formatMoney(stats.median, "USD", 2)
                  : "—"}
              </strong>
            </div>
            <div className="ebay-cluster-metric">
              <span>{t("ebay_sold_range")}</span>
              <strong>
                {formatMoney(stats.min, "USD", 2)} –{" "}
                {formatMoney(stats.max, "USD", 2)}
              </strong>
            </div>
            <div className="ebay-cluster-metric">
              <span>{t("ebay_sold_n")}</span>
              <strong>{stats.n}</strong>
            </div>
          </div>
        ) : null}
        {sold.length > 0 ? (
          <div className="ebay-list">
            {sold.map((row, idx) => (
              <EbayRow key={`${row.item_id || row.url || idx}-s`} row={row} />
            ))}
          </div>
        ) : null}
        {!loading && data?.sold_fallback_active && fallback.length > 0 ? (
          <>
            <p className="ebay-caption">{t("ebay_sold_proxy")}</p>
            <div className="ebay-list">
              {fallback.map((row, idx) => (
                <EbayRow key={`${row.item_id || row.url || idx}-f`} row={row} />
              ))}
            </div>
          </>
        ) : null}
      </div>

      <div className="ebay-block">
        <div className="ebay-head">
          <h2>{t("ebay_active_title")}</h2>
          <p>{t("ebay_active_lede")}</p>
        </div>
        {!loading &&
        (error || (data && !data.configured) || data?.listings_error) ? (
          <p className="empty-state">{t("ebay_unavailable")}</p>
        ) : null}
        {!loading &&
        data?.configured &&
        !data.listings_error &&
        listings.length === 0 ? (
          <p className="empty-state">{t("ebay_empty")}</p>
        ) : null}
        {listings.length > 0 ? (
          <>
            {lowest.length ? (
              <p className="ebay-caption">
                {t("ebay_active_from", {
                  price: formatMoney(Math.min(...lowest), "USD", 2),
                  n: listings.length,
                })}
              </p>
            ) : null}
            {data?.epn ? (
              <p className="ebay-caption">{t("ebay_epn")}</p>
            ) : null}
            <div className="ebay-list">
              {listings.map((row, idx) => (
                <EbayRow key={`${row.item_id || row.url || idx}-a`} row={row} />
              ))}
            </div>
          </>
        ) : null}
      </div>
    </section>
  );
}

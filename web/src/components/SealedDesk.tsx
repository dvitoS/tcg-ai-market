"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState, useTransition } from "react";

import { useCurrency } from "@/components/CurrencyProvider";
import { DeskLoading } from "@/components/DeskLoading";
import { useLocale } from "@/components/LocaleProvider";
import { fetchSealedQuote } from "@/lib/api";
import type { SealedQuoteItem, SealedQuoteResponse } from "@/lib/types";

export function SealedDesk({
  initial = null,
}: {
  initial?: SealedQuoteResponse | null;
}) {
  const { t } = useLocale();
  const { formatSpot } = useCurrency();
  const ssrBoot = Boolean(initial?.items?.length);
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [items, setItems] = useState<SealedQuoteItem[]>(
    () => initial?.items ?? [],
  );
  const [source, setSource] = useState<string>(() => initial?.source ?? "");
  const [justtcg, setJusttcg] = useState(() =>
    Boolean(initial?.justtcg_configured),
  );
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [booted, setBooted] = useState(ssrBoot);

  const load = useCallback(
    (q: string) => {
      startTransition(async () => {
        setError(null);
        try {
          const payload = await fetchSealedQuote({
            q: q || undefined,
            limit: 48,
          });
          setItems(payload.items);
          setSource(payload.source);
          setJusttcg(Boolean(payload.justtcg_configured));
          if (q && !payload.items.length) {
            setError(payload.error || t("sealed_empty"));
          }
        } catch (err) {
          setItems([]);
          setError(err instanceof Error ? err.message : t("sealed_error"));
        } finally {
          setBooted(true);
        }
      });
    },
    [t],
  );

  useEffect(() => {
    // RSC already painted the curated showcase — skip the empty-desk round-trip.
    if (ssrBoot) return;
    load("");
  }, [load, ssrBoot]);

  function onSearch(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    setSubmitted(q);
    load(q);
  }

  return (
    <section className="sealed-desk">
      <div className="explore-command">
        <p className="explore-command-eyebrow">{t("sealed_desk_eyebrow")}</p>
        <h1 className="explore-title">{t("sealed_desk_title")}</h1>
        <p className="explore-lede">{t("sealed_desk_lede")}</p>
      </div>

      <form className="search-strip scanner-search" onSubmit={onSearch}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("sealed_search_ph")}
          aria-label={t("sealed_search_aria")}
        />
        <button type="submit" className="btn-primary" disabled={pending}>
          {pending ? t("sealed_searching") : t("sealed_search_btn")}
        </button>
      </form>

      {source === "justtcg" && !submitted ? (
        <p className="lot-meta">{t("sealed_desk_live")}</p>
      ) : null}
      {source === "demo" && !submitted ? (
        <p className="lot-meta">
          {justtcg ? t("sealed_desk_seed_fast") : t("sealed_demo_note")}
        </p>
      ) : null}
      {source === "demo" && submitted ? (
        <p className="lot-meta">{t("sealed_desk_demo_live")}</p>
      ) : null}
      {submitted ? (
        <p className="lot-meta">
          {t("sealed_desk_results", { q: submitted, n: items.length })}
        </p>
      ) : (
        <p className="lot-meta">{t("sealed_desk_showcase")}</p>
      )}
      <p className="lot-meta">{t("sealed_desk_disclaimer")}</p>

      {error ? <p className="banner-error">{error}</p> : null}

      {!booted || (pending && items.length === 0) ? (
        <DeskLoading label={t("sealed_searching")} variant="panel" skeletonCount={3} />
      ) : items.length === 0 ? (
        <p className="empty-state">{t("sealed_empty")}</p>
      ) : (
        <div className={`explore-grid sealed-desk-grid ${pending ? "is-pending" : ""}`}>
          {items.map((hit) => {
            const detailHref = hit.tcgplayer_id
              ? `/sealed/${encodeURIComponent(hit.tcgplayer_id)}`
              : "/sealed";
            return (
              <Link
                key={hit.card_id}
                href={detailHref}
                className="sealed-desk-card sealed-desk-card-link"
              >
                <div className="sealed-desk-art">
                  <Image
                    src={hit.image_url || "/kestrel-logo.png"}
                    alt={hit.name}
                    width={245}
                    height={245}
                    className="sealed-desk-img"
                    sizes="(max-width: 640px) 45vw, 180px"
                  />
                  <div className="explore-card-readout">
                    <span className="explore-card-price">
                      {formatSpot(hit.spot_usd)}
                    </span>
                  </div>
                </div>
                <div className="explore-card-copy">
                  <div className="explore-card-name">{hit.name}</div>
                  <div className="explore-card-meta">
                    {[hit.set_name, hit.tcgplayer_id].filter(Boolean).join(" · ")}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}

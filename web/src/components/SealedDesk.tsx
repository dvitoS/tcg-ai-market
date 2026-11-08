"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState, useTransition } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useCurrency } from "@/components/CurrencyProvider";
import { DeskLoading } from "@/components/DeskLoading";
import { useLocale } from "@/components/LocaleProvider";
import {
  addPortfolioLot,
  ensureSealedCard,
  fetchSealedQuote,
} from "@/lib/api";
import type { SealedQuoteItem } from "@/lib/types";

export function SealedDesk() {
  const { t } = useLocale();
  const { formatSpot } = useCurrency();
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [items, setItems] = useState<SealedQuoteItem[]>([]);
  const [source, setSource] = useState<string>("");
  const [justtcg, setJusttcg] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [selected, setSelected] = useState<SealedQuoteItem | null>(null);
  const [qty, setQty] = useState(1);
  const [cost, setCost] = useState(0);
  const [pending, startTransition] = useTransition();
  const [booted, setBooted] = useState(false);

  const load = useCallback(
    (q: string) => {
      startTransition(async () => {
        setError(null);
        setNote(null);
        try {
          const payload = await fetchSealedQuote({
            q: q || undefined,
            limit: 12,
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
    load("");
  }, [load]);

  function onSearch(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    setSubmitted(q);
    setSelected(null);
    load(q);
  }

  function pick(hit: SealedQuoteItem) {
    setSelected(hit);
    setCost(
      hit.spot_usd != null && Number.isFinite(Number(hit.spot_usd))
        ? Number(hit.spot_usd)
        : 0,
    );
    setNote(null);
    setError(null);
  }

  async function onAdd(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    if (!user) return;
    if (!(Number(cost) > 0)) {
      setError(t("sealed_need_cost"));
      return;
    }
    setError(null);
    setNote(null);
    try {
      const ensured = await ensureSealedCard(selected);
      await addPortfolioLot({
        card_id: ensured.card_id,
        quantity: Math.max(1, Math.floor(qty) || 1),
        purchase_price: Number(cost),
        condition: "NM",
        printing: "Normal",
      });
      setNote(t("sealed_added", { name: ensured.name }));
      setSelected(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("sealed_error"));
    }
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
      {source === "demo" ? (
        <p className="lot-meta">
          {justtcg ? t("sealed_desk_demo_live") : t("sealed_demo_note")}
        </p>
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
      {note ? <p className="banner-ok">{note}</p> : null}

      {!booted || (pending && items.length === 0) ? (
        <DeskLoading label={t("sealed_searching")} variant="panel" skeletonCount={3} />
      ) : items.length === 0 ? (
        <p className="empty-state">{t("sealed_empty")}</p>
      ) : (
        <div className={`explore-grid sealed-desk-grid ${pending ? "is-pending" : ""}`}>
          {items.map((hit) => (
            <button
              key={hit.card_id}
              type="button"
              className={`sealed-desk-card ${selected?.card_id === hit.card_id ? "is-selected" : ""}`}
              onClick={() => pick(hit)}
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
            </button>
          ))}
        </div>
      )}

      {selected ? (
        <div className="sealed-desk-dock">
          <div className="sealed-desk-dock-copy">
            <p className="lot-name">{selected.name}</p>
            <p className="lot-meta">
              {t("sealed_selected", { name: selected.name })} ·{" "}
              {formatSpot(selected.spot_usd)}
            </p>
          </div>
          {user ? (
            <form className="sealed-add-form sealed-desk-add" onSubmit={onAdd}>
              <div className="grade-ev-inputs">
                <label>
                  <span>{t("add_lot_qty")}</span>
                  <input
                    type="number"
                    min={1}
                    step={1}
                    value={qty}
                    onChange={(e) => setQty(Number(e.target.value) || 1)}
                  />
                </label>
                <label>
                  <span>{t("add_lot_cost")}</span>
                  <input
                    type="number"
                    min={0.01}
                    step={0.01}
                    value={cost}
                    onChange={(e) => setCost(Number(e.target.value) || 0)}
                  />
                </label>
              </div>
              <button type="submit" className="btn-primary" disabled={pending}>
                {t("sealed_add_btn")}
              </button>
            </form>
          ) : (
            <Link
              href={`/signin?next=${encodeURIComponent("/sealed")}`}
              className="btn-primary"
            >
              {t("sealed_desk_signin")}
            </Link>
          )}
        </div>
      ) : null}
    </section>
  );
}

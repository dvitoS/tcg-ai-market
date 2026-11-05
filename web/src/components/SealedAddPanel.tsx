"use client";

import { FormEvent, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import {
  addPortfolioLot,
  ensureSealedCard,
  fetchSealedQuote,
  formatMoney,
} from "@/lib/api";
import type { SealedQuoteItem } from "@/lib/types";

export function SealedAddPanel({ onAdded }: { onAdded?: () => void }) {
  const { t } = useLocale();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SealedQuoteItem[]>([]);
  const [source, setSource] = useState<string>("");
  const [selected, setSelected] = useState<SealedQuoteItem | null>(null);
  const [qty, setQty] = useState(1);
  const [cost, setCost] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  async function onSearch(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    if (!q) return;
    setBusy(true);
    setError(null);
    setNote(null);
    setSelected(null);
    try {
      const payload = await fetchSealedQuote({ q, limit: 8 });
      setHits(payload.items);
      setSource(payload.source);
      if (!payload.items.length) {
        setError(payload.error || t("sealed_empty"));
      }
    } catch (err) {
      setHits([]);
      setError(err instanceof Error ? err.message : t("sealed_error"));
    } finally {
      setBusy(false);
    }
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
    if (!(Number(cost) > 0)) {
      setError(t("sealed_need_cost"));
      return;
    }
    setBusy(true);
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
      setHits([]);
      setQuery("");
      onAdded?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("sealed_error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="sealed-add-panel" aria-label={t("sealed_title")}>
      <div className="detail-ai-head">
        <h2>{t("sealed_title")}</h2>
      </div>
      <p className="grade-ev-lede">{t("sealed_lede")}</p>

      <form className="search-strip scanner-search" onSubmit={onSearch}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("sealed_search_ph")}
          aria-label={t("sealed_search_aria")}
        />
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? t("sealed_searching") : t("sealed_search_btn")}
        </button>
      </form>

      {source === "demo" && hits.length > 0 ? (
        <p className="lot-meta">{t("sealed_demo_note")}</p>
      ) : null}
      {error ? <p className="form-error">{error}</p> : null}
      {note ? <p className="pro-open-note">{note}</p> : null}

      {hits.length > 0 ? (
        <ul className="sealed-hit-list">
          {hits.map((hit) => (
            <li key={hit.card_id}>
              <button
                type="button"
                className={`sealed-hit ${selected?.card_id === hit.card_id ? "is-selected" : ""}`}
                onClick={() => pick(hit)}
              >
                <span className="sealed-hit-name">{hit.name}</span>
                <span className="lot-meta">
                  {[hit.set_name, hit.tcgplayer_id]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
                <strong>
                  {hit.spot_usd != null
                    ? formatMoney(hit.spot_usd, "USD", 2)
                    : "—"}
                </strong>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {selected ? (
        <form className="sealed-add-form" onSubmit={onAdd}>
          <p className="lot-meta">
            {t("sealed_selected", { name: selected.name })}
          </p>
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
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? t("add_lot_busy") : t("sealed_add_btn")}
          </button>
        </form>
      ) : null}
    </section>
  );
}

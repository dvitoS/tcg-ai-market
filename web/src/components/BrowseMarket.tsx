"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState, useTransition } from "react";

import { CardSkeletonGrid } from "@/components/CardSkeletonGrid";
import { ExploreCard } from "@/components/ExploreCard";
import { fetchCatalog } from "@/lib/api";
import type { CatalogCard, CatalogMeta, CatalogMode } from "@/lib/types";

const BATCH = 24;

function parsePrice(raw: string): number | undefined {
  const text = raw.trim();
  if (!text) return undefined;
  const n = Number(text);
  return Number.isFinite(n) && n >= 0 ? n : undefined;
}

type Props = {
  initialItems: CatalogCard[];
  initialTotal: number;
  initialMeta: CatalogMeta;
  initialError?: string | null;
};

export function BrowseMarket({
  initialItems,
  initialTotal,
  initialMeta,
  initialError = null,
}: Props) {
  const [mode, setMode] = useState<CatalogMode>("browse");
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [setName, setSetName] = useState("");
  const [signal, setSignal] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [items, setItems] = useState(initialItems);
  const [total, setTotal] = useState(initialTotal);
  const [meta, setMeta] = useState(initialMeta);
  const [error, setError] = useState<string | null>(initialError);
  const [pending, startTransition] = useTransition();
  const [hydrated, setHydrated] = useState(false);

  const load = useCallback(
    (offset: number, append: boolean) => {
      startTransition(async () => {
        try {
          const data = await fetchCatalog({
            q: submittedQuery || undefined,
            set: setName || undefined,
            signal: mode === "signals" ? signal || undefined : undefined,
            min_price: parsePrice(minPrice),
            max_price: parsePrice(maxPrice),
            mode,
            limit: BATCH,
            offset,
            sort: mode === "signals" ? "change_desc" : "price_desc",
          });
          setMeta(data.meta);
          setTotal(data.total);
          setItems((prev) => (append ? [...prev, ...data.items] : data.items));
          setError(null);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to load catalog");
        }
      });
    },
    [mode, setName, signal, submittedQuery, minPrice, maxPrice],
  );

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    load(0, false);
  }, [hydrated, load]);

  function onSearch(event: FormEvent) {
    event.preventDefault();
    setSubmittedQuery(query.trim());
  }

  function onClear() {
    setQuery("");
    setSubmittedQuery("");
    setSetName("");
    setSignal("");
    setMinPrice("");
    setMaxPrice("");
  }

  const sets = useMemo(() => meta.sets || [], [meta.sets]);
  const canLoadMore = items.length < total;

  return (
    <section className="browse">
      <div className="explore-command">
        <p className="explore-command-eyebrow">Browse market</p>
        <h1 className="explore-title">Market</h1>
        <p className="explore-lede">
          Pokémon TCG prices and AI signals — art-first, mobile-ready.
        </p>
      </div>

      <div className="mode-toggle" role="tablist" aria-label="Catalog mode">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "browse"}
          className={mode === "browse" ? "is-active" : ""}
          onClick={() => setMode("browse")}
        >
          Browse
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "signals"}
          className={mode === "signals" ? "is-active" : ""}
          onClick={() => setMode("signals")}
          id="signals"
        >
          AI signals
        </button>
      </div>

      <form className="search-strip" onSubmit={onSearch}>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name, set, or id…"
          aria-label="Search cards"
        />
        <button type="submit" className="btn-primary">
          Search
        </button>
        <button type="button" className="btn-ghost" onClick={onClear}>
          Clear
        </button>
      </form>

      <div className="filter-row">
        <label>
          <span>Set</span>
          <select value={setName} onChange={(e) => setSetName(e.target.value)}>
            <option value="">All sets</option>
            {sets.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        {mode === "signals" ? (
          <label>
            <span>Signal</span>
            <select value={signal} onChange={(e) => setSignal(e.target.value)}>
              <option value="">All</option>
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
              <option value="HOLD">HOLD</option>
            </select>
          </label>
        ) : null}
        <label>
          <span>Min $</span>
          <input
            type="number"
            min={0}
            step={1}
            inputMode="decimal"
            value={minPrice}
            onChange={(e) => setMinPrice(e.target.value)}
            placeholder="0"
          />
        </label>
        <label>
          <span>Max $</span>
          <input
            type="number"
            min={0}
            step={1}
            inputMode="decimal"
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            placeholder="Any"
          />
        </label>
        <p className="result-count">
          {total} cards
          {meta.source === "demo" ? " · demo seed" : null}
          {pending ? " · updating…" : null}
        </p>
      </div>

      {error ? <p className="banner-error">{error}</p> : null}

      {pending && items.length === 0 ? (
        <CardSkeletonGrid />
      ) : items.length === 0 ? (
        <p className="empty-state">No cards match these filters. Try clearing price or set.</p>
      ) : (
        <div className={`explore-grid ${pending ? "is-pending" : ""}`}>
          {items.map((card) => (
            <ExploreCard key={card.id} card={card} showSignal={mode === "signals"} />
          ))}
        </div>
      )}

      {canLoadMore ? (
        <div className="load-more-wrap">
          <button
            type="button"
            className="btn-primary"
            disabled={pending}
            onClick={() => load(items.length, true)}
          >
            Load more
          </button>
        </div>
      ) : null}
    </section>
  );
}

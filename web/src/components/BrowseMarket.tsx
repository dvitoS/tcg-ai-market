"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState, useTransition } from "react";

import { CardSkeletonGrid } from "@/components/CardSkeletonGrid";
import { ExploreCard } from "@/components/ExploreCard";
import { useLocale } from "@/components/LocaleProvider";
import { SearchSuggest } from "@/components/SearchSuggest";
import { fetchCatalog } from "@/lib/api";
import { signalLabel } from "@/lib/i18n/messages";
import { pushRecentSearch } from "@/lib/searchRecent";
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
  const { locale, t } = useLocale();
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

  function applyQuery(next: string) {
    const q = next.trim();
    setQuery(q);
    if (q) pushRecentSearch("browse", q);
    setSubmittedQuery(q);
  }

  function onSearch(event: FormEvent) {
    event.preventDefault();
    applyQuery(query);
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
        <p className="explore-command-eyebrow">{t("explore_eyebrow")}</p>
        <h1 className="explore-title">{t("explore_title")}</h1>
        <p className="explore-lede">{t("explore_lede")}</p>
      </div>

      <div className="mode-toggle" role="tablist" aria-label={t("catalog_mode")}>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "browse"}
          className={mode === "browse" ? "is-active" : ""}
          onClick={() => setMode("browse")}
        >
          {t("catalog_browse")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "signals"}
          className={mode === "signals" ? "is-active" : ""}
          onClick={() => setMode("signals")}
          id="signals"
        >
          {t("catalog_signals")}
        </button>
      </div>

      <form className="search-strip" onSubmit={onSearch}>
        <SearchSuggest
          value={query}
          onChange={setQuery}
          onCommit={applyQuery}
          placeholder={t("explore_search_ph")}
          ariaLabel={t("explore_search_aria")}
          recentScope="browse"
        />
        <button type="submit" className="btn-primary">
          {t("explore_search_btn")}
        </button>
        <button type="button" className="btn-ghost" onClick={onClear}>
          {t("explore_clear")}
        </button>
      </form>

      <div className="filter-row">
        <label>
          <span>{t("explore_set")}</span>
          <select value={setName} onChange={(e) => setSetName(e.target.value)}>
            <option value="">{t("explore_all_sets")}</option>
            {sets.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        {mode === "signals" ? (
          <label>
            <span>{t("explore_signal")}</span>
            <select value={signal} onChange={(e) => setSignal(e.target.value)}>
              <option value="">{t("explore_all")}</option>
              <option value="BUY">{signalLabel(locale, "BUY")}</option>
              <option value="SELL">{signalLabel(locale, "SELL")}</option>
              <option value="HOLD">{signalLabel(locale, "HOLD")}</option>
            </select>
          </label>
        ) : null}
        <label>
          <span>{t("explore_min")}</span>
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
          <span>{t("explore_max")}</span>
          <input
            type="number"
            min={0}
            step={1}
            inputMode="decimal"
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            placeholder={t("explore_any")}
          />
        </label>
        <p className="result-count">
          {t("explore_results", { n: total })}
          {meta.source === "demo" ? ` · ${t("explore_demo")}` : null}
          {pending ? ` · ${t("explore_updating")}` : null}
        </p>
      </div>

      {error ? <p className="banner-error">{error}</p> : null}

      {pending && items.length === 0 ? (
        <CardSkeletonGrid />
      ) : items.length === 0 ? (
        <p className="empty-state">{t("explore_empty")}</p>
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
            {t("explore_load_more")}
          </button>
        </div>
      ) : null}
    </section>
  );
}

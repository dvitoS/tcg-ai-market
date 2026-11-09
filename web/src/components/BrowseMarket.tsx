"use client";

import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useTransition,
} from "react";

import { CardSkeletonGrid } from "@/components/CardSkeletonGrid";
import { ExploreCard } from "@/components/ExploreCard";
import { useLocale } from "@/components/LocaleProvider";
import { SearchSuggest } from "@/components/SearchSuggest";
import { fetchCatalog } from "@/lib/api";
import { signalLabel, type MessageKey } from "@/lib/i18n/messages";
import { pushRecentSearch } from "@/lib/searchRecent";
import type { CatalogCard, CatalogMeta, CatalogMode } from "@/lib/types";

const BATCH = 24;

type PriceBandId = "any" | "u5" | "5_25" | "25_100" | "100p" | "custom";

const PRICE_BANDS: Array<{
  id: Exclude<PriceBandId, "custom">;
  min: string;
  max: string;
}> = [
  { id: "any", min: "", max: "" },
  { id: "u5", min: "0", max: "5" },
  { id: "5_25", min: "5", max: "25" },
  { id: "25_100", min: "25", max: "100" },
  { id: "100p", min: "100", max: "" },
];

const BAND_LABEL: Record<Exclude<PriceBandId, "custom">, MessageKey> = {
  any: "explore_band_any",
  u5: "explore_band_u5",
  "5_25": "explore_band_5_25",
  "25_100": "explore_band_25_100",
  "100p": "explore_band_100p",
};

function parsePrice(raw: string): number | undefined {
  const text = raw.trim();
  if (!text) return undefined;
  const n = Number(text);
  return Number.isFinite(n) && n >= 0 ? n : undefined;
}

function matchPriceBand(minPrice: string, maxPrice: string): PriceBandId {
  const min = minPrice.trim();
  const max = maxPrice.trim();
  for (const band of PRICE_BANDS) {
    if (band.min === min && band.max === max) return band.id;
  }
  if (!min && !max) return "any";
  return "custom";
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
  const [setNeedle, setSetNeedle] = useState("");
  const [signal, setSignal] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [railOpen, setRailOpen] = useState(false);
  const [items, setItems] = useState(initialItems);
  const [total, setTotal] = useState(initialTotal);
  const [meta, setMeta] = useState(initialMeta);
  const [error, setError] = useState<string | null>(initialError);
  const [pending, startTransition] = useTransition();
  const [hydrated, setHydrated] = useState(false);
  // Keep SSR catalog on first paint — only refetch when filters/mode change.
  const skipNextLoad = useRef(true);

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
        } catch {
          setError(t("explore_load_failed"));
        }
      });
    },
    [mode, setName, signal, submittedQuery, minPrice, maxPrice, t],
  );

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (skipNextLoad.current) {
      skipNextLoad.current = false;
      return;
    }
    load(0, false);
  }, [hydrated, load]);

  useEffect(() => {
    if (!railOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setRailOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [railOpen]);

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
    setSetNeedle("");
    setSignal("");
    setMinPrice("");
    setMaxPrice("");
  }

  function applyPriceBand(id: Exclude<PriceBandId, "custom">) {
    const band = PRICE_BANDS.find((row) => row.id === id);
    if (!band) return;
    setMinPrice(band.min);
    setMaxPrice(band.max);
  }

  const sets = useMemo(() => meta.sets || [], [meta.sets]);
  const filteredSets = useMemo(() => {
    const needle = setNeedle.trim().toLowerCase();
    if (!needle) return sets;
    return sets.filter((name) => name.toLowerCase().includes(needle));
  }, [sets, setNeedle]);

  const priceBand = matchPriceBand(minPrice, maxPrice);
  const canLoadMore = items.length < total;
  const activeFilterCount =
    Number(Boolean(setName)) +
    Number(Boolean(signal) && mode === "signals") +
    Number(Boolean(minPrice.trim()) || Boolean(maxPrice.trim())) +
    Number(Boolean(submittedQuery));

  const signalCounts = meta.signals || {};

  const rail = (
    <aside
      className={`browse-rail ${railOpen ? "is-open" : ""}`}
      aria-label={t("explore_filters")}
    >
      <div className="browse-rail-head">
        <div>
          <p className="browse-rail-kicker">{t("explore_filters")}</p>
          <p className="browse-rail-count">
            {t("explore_results", { n: total })}
            {meta.source === "demo" ? ` · ${t("explore_demo")}` : null}
            {pending ? ` · ${t("explore_updating")}` : null}
          </p>
        </div>
        <button
          type="button"
          className="browse-rail-close"
          onClick={() => setRailOpen(false)}
          aria-label={t("explore_filters_close")}
        >
          ×
        </button>
      </div>

      {activeFilterCount > 0 ? (
        <div className="browse-active" aria-label={t("explore_active_filters")}>
          {submittedQuery ? (
            <button
              type="button"
              className="browse-chip"
              onClick={() => {
                setQuery("");
                setSubmittedQuery("");
              }}
            >
              “{submittedQuery}”
              <span aria-hidden>×</span>
            </button>
          ) : null}
          {setName ? (
            <button
              type="button"
              className="browse-chip"
              onClick={() => setSetName("")}
            >
              {setName}
              <span aria-hidden>×</span>
            </button>
          ) : null}
          {mode === "signals" && signal ? (
            <button
              type="button"
              className="browse-chip"
              onClick={() => setSignal("")}
            >
              {signalLabel(locale, signal)}
              <span aria-hidden>×</span>
            </button>
          ) : null}
          {minPrice.trim() || maxPrice.trim() ? (
            <button
              type="button"
              className="browse-chip"
              onClick={() => {
                setMinPrice("");
                setMaxPrice("");
              }}
            >
              {minPrice.trim() || "0"}–{maxPrice.trim() || "∞"}
              <span aria-hidden>×</span>
            </button>
          ) : null}
          <button type="button" className="browse-clear-link" onClick={onClear}>
            {t("explore_clear_all")}
          </button>
        </div>
      ) : null}

      <div className="browse-rail-group">
        <div className="browse-rail-label-row">
          <span>{t("explore_set")}</span>
          {setName ? (
            <button
              type="button"
              className="browse-clear-link"
              onClick={() => setSetName("")}
            >
              {t("explore_all_sets")}
            </button>
          ) : null}
        </div>
        <input
          className="browse-set-search"
          type="search"
          value={setNeedle}
          onChange={(e) => setSetNeedle(e.target.value)}
          placeholder={t("explore_set_search")}
          aria-label={t("explore_set_search")}
        />
        <div className="browse-set-list" role="listbox" aria-label={t("explore_set")}>
          <button
            type="button"
            role="option"
            aria-selected={!setName}
            className={`browse-set-option ${!setName ? "is-active" : ""}`}
            onClick={() => setSetName("")}
          >
            <span>{t("explore_all_sets")}</span>
          </button>
          {filteredSets.map((name) => (
            <button
              key={name}
              type="button"
              role="option"
              aria-selected={setName === name}
              className={`browse-set-option ${setName === name ? "is-active" : ""}`}
              onClick={() => {
                setSetName(name);
                setRailOpen(false);
              }}
              title={name}
            >
              <span>{name}</span>
            </button>
          ))}
          {filteredSets.length === 0 ? (
            <p className="browse-set-empty">{t("explore_set_empty")}</p>
          ) : null}
        </div>
      </div>

      <div className="browse-rail-group">
        <span className="browse-rail-label">{t("explore_price")}</span>
        <div className="browse-price-bands" role="group" aria-label={t("explore_price")}>
          {PRICE_BANDS.map((band) => (
            <button
              key={band.id}
              type="button"
              className={`browse-band ${priceBand === band.id ? "is-active" : ""}`}
              onClick={() => applyPriceBand(band.id)}
            >
              {t(BAND_LABEL[band.id])}
            </button>
          ))}
        </div>
        <div className="browse-price-inputs">
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
          <span className="browse-price-sep" aria-hidden>
            —
          </span>
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
        </div>
      </div>

      {mode === "signals" ? (
        <div className="browse-rail-group">
          <span className="browse-rail-label">{t("explore_signal")}</span>
          <div className="browse-signal-stack" role="group" aria-label={t("explore_signal")}>
            {(
              [
                { id: "", label: t("explore_all"), count: null as number | null },
                {
                  id: "BUY",
                  label: signalLabel(locale, "BUY"),
                  count: signalCounts.BUY ?? null,
                },
                {
                  id: "SELL",
                  label: signalLabel(locale, "SELL"),
                  count: signalCounts.SELL ?? null,
                },
                {
                  id: "HOLD",
                  label: signalLabel(locale, "HOLD"),
                  count: signalCounts.HOLD ?? null,
                },
              ] as const
            ).map((row) => (
              <button
                key={row.id || "all"}
                type="button"
                className={`browse-signal ${signal === row.id ? "is-active" : ""} ${
                  row.id ? `is-${row.id.toLowerCase()}` : ""
                }`}
                onClick={() => setSignal(row.id)}
              >
                <span>{row.label}</span>
                {row.count != null ? (
                  <em>{row.count}</em>
                ) : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </aside>
  );

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

      <div className="browse-toolbar">
        <button
          type="button"
          className="browse-rail-open"
          onClick={() => setRailOpen(true)}
          aria-expanded={railOpen}
        >
          {t("explore_filters")}
          {activeFilterCount > 0 ? (
            <span className="browse-rail-badge">{activeFilterCount}</span>
          ) : null}
        </button>
        <p className="browse-toolbar-count">
          {t("explore_results", { n: total })}
          {pending ? ` · ${t("explore_updating")}` : null}
        </p>
      </div>

      <div className="browse-desk">
        {railOpen ? (
          <button
            type="button"
            className="browse-rail-scrim"
            aria-label={t("explore_filters_close")}
            onClick={() => setRailOpen(false)}
          />
        ) : null}
        {rail}

        <div className="browse-main">
          {error ? <p className="banner-error">{error}</p> : null}

          {pending && items.length === 0 ? (
            <CardSkeletonGrid />
          ) : items.length === 0 ? (
            <p className="empty-state">{t("explore_empty")}</p>
          ) : (
            <div className={`explore-grid ${pending ? "is-pending" : ""}`}>
              {items.map((card, index) => (
                <ExploreCard
                  key={card.id}
                  card={card}
                  showSignal={mode === "signals"}
                  priority={index < 4}
                />
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
        </div>
      </div>
    </section>
  );
}

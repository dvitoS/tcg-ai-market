"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState, useTransition } from "react";

import { CardSkeletonGrid } from "@/components/CardSkeletonGrid";
import { DeskLoading } from "@/components/DeskLoading";
import { ExploreCard } from "@/components/ExploreCard";
import { useLocale } from "@/components/LocaleProvider";
import { SearchSuggest } from "@/components/SearchSuggest";
import { fetchScanner, formatChange, formatMoney } from "@/lib/api";
import { pushRecentSearch } from "@/lib/searchRecent";
import type { ScannerCard, ScannerResponse } from "@/lib/types";

function parsePrice(raw: string): number | undefined {
  const text = raw.trim();
  if (!text) return undefined;
  const n = Number(text);
  return Number.isFinite(n) && n >= 0 ? n : undefined;
}

const EMPTY: ScannerResponse = {
  forecast_days: 7,
  growth_floor: 10,
  min_growth: 10,
  scoped: 0,
  opp_total: 0,
  warn_total: 0,
  sets: [],
  rarities: [],
  opportunities: [],
  warnings: [],
  source: "empty",
};

function ScanRow({ card }: { card: ScannerCard }) {
  return (
    <Link href={`/cards/${encodeURIComponent(card.id)}`} className="scan-row">
      <div className="scan-art">
        <Image
          src={card.image_url || "/kestrel-logo.png"}
          alt={card.name}
          width={48}
          height={67}
        />
      </div>
      <div>
        <div className="lot-name">{card.name}</div>
        <div className="lot-meta">
          {[card.set_name, card.rarity].filter(Boolean).join(" · ")}
        </div>
      </div>
      <div className="scan-metrics">
        <strong>{formatMoney(card.current_price ?? card.price)}</strong>
        <span>→ {formatMoney(card.ai_target_price ?? card.predicted_price)}</span>
        <span className={(card.expected_roi_pct ?? 0) >= 0 ? "pnl-up" : "pnl-down"}>
          {formatChange(card.expected_roi_pct ?? card.expected_change_pct)}
        </span>
      </div>
    </Link>
  );
}

export function ScannerView() {
  const { t } = useLocale();
  const [data, setData] = useState<ScannerResponse>(EMPTY);
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [setName, setSetName] = useState("");
  const [rarity, setRarity] = useState("");
  const [minGrowth, setMinGrowth] = useState(5);
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [hydrated, setHydrated] = useState(false);
  const [booted, setBooted] = useState(false);

  const load = useCallback(() => {
    startTransition(async () => {
      try {
        const next = await fetchScanner({
          q: submitted || undefined,
          set: setName || undefined,
          rarity: rarity || undefined,
          min_price: parsePrice(minPrice),
          max_price: parsePrice(maxPrice),
          min_growth: minGrowth,
          limit: 24,
        });
        setData(next);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Scanner failed");
      } finally {
        setBooted(true);
      }
    });
  }, [submitted, setName, rarity, minGrowth, minPrice, maxPrice]);

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    load();
  }, [hydrated, load]);

  function applyQuery(next: string) {
    const q = next.trim();
    setQuery(q);
    if (q) pushRecentSearch("scanner", q);
    setSubmitted(q);
  }

  function onSearch(event: FormEvent) {
    event.preventDefault();
    applyQuery(query);
  }

  if (!hydrated || !booted) {
    return (
      <section className="scanner-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("scan_eyebrow")}</p>
          <h1 className="explore-title">{t("scan_title")}</h1>
        </div>
        <DeskLoading label={t("scan_loading")} variant="panel" skeletonCount={8} />
      </section>
    );
  }

  return (
    <section className="scanner-page">
      <div className="explore-command">
        <p className="explore-command-eyebrow">{t("scan_eyebrow")}</p>
        <h1 className="explore-title">{t("scan_title")}</h1>
        <p className="explore-lede">
          {t("scan_lede", { days: data.forecast_days })}
          {data.source === "demo" ? ` · ${t("explore_demo")}` : ""}
        </p>
      </div>

      {pending ? <DeskLoading label={t("explore_updating")} variant="banner" /> : null}

      <form className="search-strip scanner-search" onSubmit={onSearch}>
        <SearchSuggest
          value={query}
          onChange={setQuery}
          onCommit={applyQuery}
          placeholder={t("scan_search_ph")}
          ariaLabel={t("scan_search_aria")}
          recentScope="scanner"
        />
        <button type="submit" className="btn-primary">
          {t("scan_btn")}
        </button>
      </form>

      <div className="filter-row">
        <label>
          <span>{t("explore_set")}</span>
          <select value={setName} onChange={(e) => setSetName(e.target.value)}>
            <option value="">{t("explore_all_sets")}</option>
            {data.sets.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("scan_rarity")}</span>
          <select value={rarity} onChange={(e) => setRarity(e.target.value)}>
            <option value="">{t("explore_all")}</option>
            {data.rarities.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("scan_min_growth")}</span>
          <input
            type="number"
            min={0}
            max={100}
            step={1}
            value={minGrowth}
            onChange={(e) => setMinGrowth(Number(e.target.value) || 0)}
          />
        </label>
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
          {t("scan_scoped_count", { n: data.scoped })}
        </p>
      </div>

      {error ? <p className="banner-error">{error}</p> : null}

      <div className="kpi-row scanner-kpis">
        <div className="kpi-chip">
          <span>{t("scan_kpi_scoped")}</span>
          <strong>{data.scoped}</strong>
        </div>
        <div className="kpi-chip pnl-up">
          <span>{t("scan_kpi_opps", { n: data.min_growth.toFixed(0) })}</span>
          <strong>{data.opp_total}</strong>
        </div>
        <div className="kpi-chip pnl-down">
          <span>{t("scan_kpi_warns")}</span>
          <strong>{data.warn_total}</strong>
        </div>
      </div>

      <div className="portfolio-section-head">
        <h2>{t("scan_opps_title")}</h2>
      </div>
      {pending && data.opportunities.length === 0 ? (
        <CardSkeletonGrid count={6} />
      ) : data.opportunities.length === 0 ? (
        <p className="empty-state">{t("scan_opps_empty")}</p>
      ) : (
        <>
          <div className={`explore-grid scanner-grid${pending ? " is-pending" : ""}`}>
            {data.opportunities.slice(0, 12).map((card) => (
              <ExploreCard key={card.id} card={card} showSignal />
            ))}
          </div>
          <div className={`scan-list${pending ? " is-pending" : ""}`}>
            {data.opportunities.map((card) => (
              <ScanRow key={`opp-${card.id}`} card={card} />
            ))}
          </div>
        </>
      )}

      <div className="portfolio-section-head">
        <h2>{t("scan_warns_title")}</h2>
      </div>
      {data.warnings.length === 0 ? (
        <p className="empty-state">{t("scan_warns_empty")}</p>
      ) : (
        <div className="scan-list">
          {data.warnings.map((card) => (
            <ScanRow key={`warn-${card.id}`} card={card} />
          ))}
        </div>
      )}
    </section>
  );
}

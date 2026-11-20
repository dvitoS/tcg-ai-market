"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState, useTransition } from "react";

import { DeskLoading } from "@/components/DeskLoading";
import { useLocale } from "@/components/LocaleProvider";
import { SearchSuggest } from "@/components/SearchSuggest";
import { fetchScanner, formatChange, formatMoney } from "@/lib/api";
import { onCardImageError, resolveCardImageUrl } from "@/lib/cardImage";
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

function ScanCardTile({
  card,
  tone,
}: {
  card: ScannerCard;
  tone: "up" | "down";
}) {
  const roi = card.expected_roi_pct ?? 0;
  const sideClass = tone === "up" ? "is-buy" : "is-sell";
  const moveClass = tone === "up" ? "up" : "down";
  return (
    <Link
      href={`/cards/${encodeURIComponent(card.id)}`}
      className={`explore-card sealed-desk-card-link ${sideClass}`}
    >
      <div className="explore-card-art">
        <Image
          src={resolveCardImageUrl(card.id, card.image_url)}
          alt={card.name}
          width={245}
          height={342}
          className="explore-card-img"
          sizes="(max-width: 640px) 45vw, 180px"
          onError={(event) => onCardImageError(event, card.id)}
        />
        <div className="explore-card-readout">
          <span className="explore-card-price">
            {formatMoney(card.current_price ?? card.price)}
          </span>
          <div className="explore-card-moves">
            <div className={`explore-card-move ${moveClass}`}>
              <span className="explore-card-move-label">AI</span>
              <span className="explore-card-move-value">
                {formatMoney(card.ai_target_price ?? card.predicted_price)}
              </span>
            </div>
          </div>
          <div
            className={`explore-card-change ${
              roi >= 0 ? "up" : "down"
            }`}
          >
            {formatChange(roi)}
          </div>
        </div>
      </div>
      <div className="explore-card-copy">
        <div className="explore-card-name">{card.name}</div>
        <div className="explore-card-meta">
          {[card.set_name, card.rarity].filter(Boolean).join(" · ")}
        </div>
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
        setError(err instanceof Error ? err.message : t("scan_error"));
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
      <section className="scanner-page desk-premium">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("scan_eyebrow")}</p>
          <h1 className="explore-title">{t("scan_title")}</h1>
        </div>
        <DeskLoading label={t("scan_loading")} variant="panel" skeletonCount={8} />
      </section>
    );
  }

  return (
    <section className="scanner-page desk-premium">
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
        <p className="result-count">
          {t("scan_scoped_count", { n: data.scoped })}
        </p>
      </div>
      <details className="desk-more-filters">
        <summary className="lot-meta">{t("radar_more_filters")}</summary>
        <div className="filter-row">
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
        </div>
      </details>

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
        <DeskLoading label={t("explore_updating")} variant="panel" skeletonCount={4} />
      ) : data.opportunities.length === 0 ? (
        <p className="empty-state">{t("scan_opps_empty")}</p>
      ) : (
        <div
          className={`explore-grid sealed-desk-grid${pending ? " is-pending" : ""}`}
        >
          {data.opportunities.map((card) => (
            <ScanCardTile key={`opp-${card.id}`} card={card} tone="up" />
          ))}
        </div>
      )}

      <div className="portfolio-section-head">
        <h2>{t("scan_warns_title")}</h2>
      </div>
      {data.warnings.length === 0 ? (
        <p className="empty-state">{t("scan_warns_empty")}</p>
      ) : (
        <div className="explore-grid sealed-desk-grid">
          {data.warnings.map((card) => (
            <ScanCardTile key={`warn-${card.id}`} card={card} tone="down" />
          ))}
        </div>
      )}
    </section>
  );
}

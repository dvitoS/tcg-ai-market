"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState, useTransition } from "react";

import { ExploreCard } from "@/components/ExploreCard";
import { fetchScanner, formatChange, formatMoney } from "@/lib/api";
import type { ScannerCard, ScannerResponse } from "@/lib/types";

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
  const [data, setData] = useState<ScannerResponse>(EMPTY);
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [setName, setSetName] = useState("");
  const [rarity, setRarity] = useState("");
  const [minGrowth, setMinGrowth] = useState(5);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const load = useCallback(() => {
    startTransition(async () => {
      try {
        const next = await fetchScanner({
          q: submitted || undefined,
          set: setName || undefined,
          rarity: rarity || undefined,
          min_growth: minGrowth,
          limit: 24,
        });
        setData(next);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Scanner failed");
      }
    });
  }, [submitted, setName, rarity, minGrowth]);

  useEffect(() => {
    load();
  }, [load]);

  function onSearch(event: FormEvent) {
    event.preventDefault();
    setSubmitted(query.trim());
  }

  return (
    <section className="scanner-page">
      <div className="explore-command">
        <p className="explore-command-eyebrow">Scanner</p>
        <h1 className="explore-title">AI scan</h1>
        <p className="explore-lede">
          Rank the market board by expected {data.forecast_days}d ROI — opportunities and drop
          warnings.
          {data.source === "demo" ? " · demo seed" : ""}
        </p>
      </div>

      <form className="search-strip scanner-search" onSubmit={onSearch}>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name…"
          aria-label="Search scanner"
        />
        <button type="submit" className="btn-primary">
          Scan
        </button>
      </form>

      <div className="filter-row">
        <label>
          <span>Set</span>
          <select value={setName} onChange={(e) => setSetName(e.target.value)}>
            <option value="">All sets</option>
            {data.sets.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Rarity</span>
          <select value={rarity} onChange={(e) => setRarity(e.target.value)}>
            <option value="">All</option>
            {data.rarities.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Min growth %</span>
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
          {data.scoped} scoped
          {pending ? " · updating…" : null}
        </p>
      </div>

      {error ? <p className="banner-error">{error}</p> : null}

      <div className="kpi-row scanner-kpis">
        <div className="kpi-chip">
          <span>Scoped</span>
          <strong>{data.scoped}</strong>
        </div>
        <div className="kpi-chip pnl-up">
          <span>Top opps ≥ {data.min_growth.toFixed(0)}%</span>
          <strong>{data.opp_total}</strong>
        </div>
        <div className="kpi-chip pnl-down">
          <span>Drop warnings</span>
          <strong>{data.warn_total}</strong>
        </div>
      </div>

      <div className="portfolio-section-head">
        <h2>Top opportunities</h2>
      </div>
      {data.opportunities.length === 0 ? (
        <p className="empty-state">No opportunities at this growth floor.</p>
      ) : (
        <>
          <div className="explore-grid scanner-grid">
            {data.opportunities.slice(0, 12).map((card) => (
              <ExploreCard key={card.id} card={card} showSignal />
            ))}
          </div>
          <div className="scan-list">
            {data.opportunities.map((card) => (
              <ScanRow key={`opp-${card.id}`} card={card} />
            ))}
          </div>
        </>
      )}

      <div className="portfolio-section-head">
        <h2>Drop warnings</h2>
      </div>
      {data.warnings.length === 0 ? (
        <p className="empty-state">No negative ROI rows in this filter.</p>
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

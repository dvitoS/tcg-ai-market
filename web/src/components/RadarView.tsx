"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState, useTransition } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useLocale } from "@/components/LocaleProvider";
import {
  fetchRadar,
  fetchRadarStatus,
  formatChange,
  formatMoney,
} from "@/lib/api";
import type { RadarCard, RadarResponse, RadarStatus } from "@/lib/types";

function parsePrice(raw: string): number | undefined {
  const text = raw.trim();
  if (!text) return undefined;
  const n = Number(text);
  return Number.isFinite(n) && n >= 0 ? n : undefined;
}

const EMPTY: RadarResponse = {
  forecast_days: 7,
  edge_floor: 0,
  min_edge: 0,
  scoped: 0,
  sure_scoped: 0,
  under_total: 0,
  over_total: 0,
  sets: [],
  rarities: [],
  underpriced: [],
  overpriced: [],
  source: "empty",
};

function RadarRow({ card }: { card: RadarCard }) {
  const band =
    card.pred_lo_pct != null && card.pred_hi_pct != null
      ? `${formatChange(card.pred_lo_pct, 1)}…${formatChange(card.pred_hi_pct, 1)}`
      : null;
  const edgeUp = (card.edge_pct ?? 0) >= 0;
  return (
    <Link
      href={`/cards/${encodeURIComponent(card.id)}`}
      className={`scan-row radar-row ${card.side === "UNDER" ? "radar-under" : "radar-over"}`}
    >
      <div className="scan-art">
        <Image
          src={card.image_url || "/kestrel-logo.png"}
          alt={card.name}
          width={48}
          height={67}
        />
      </div>
      <div>
        <div className="radar-side">{card.side}</div>
        <div className="lot-name">{card.name}</div>
        <div className="lot-meta">
          {[card.set_name, card.rarity, band ? `PI ${band}` : null]
            .filter(Boolean)
            .join(" · ")}
        </div>
      </div>
      <div className="scan-metrics">
        <strong>{formatMoney(card.spot ?? card.price)}</strong>
        <span>fair {formatMoney(card.fair_price ?? card.predicted_price)}</span>
        <span className={edgeUp ? "pnl-up" : "pnl-down"}>
          edge {formatChange(card.edge_pct)}
        </span>
      </div>
    </Link>
  );
}

export function RadarView() {
  const { t } = useLocale();
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<RadarStatus | null>(null);
  const [data, setData] = useState<RadarResponse>(EMPTY);
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [setName, setSetName] = useState("");
  const [rarity, setRarity] = useState("");
  const [minEdge, setMinEdge] = useState(0);
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (authLoading || !hydrated) return;
    if (!user) {
      setStatus(null);
      return;
    }
    startTransition(async () => {
      try {
        const st = await fetchRadarStatus();
        setStatus(st);
        setMinEdge(st.edge_floor);
        setError(null);
      } catch (err) {
        setStatus(null);
        setError(err instanceof Error ? err.message : t("radar_error"));
      }
    });
  }, [authLoading, user, hydrated, t]);

  const load = useCallback(() => {
    if (!user || !status?.allowed) return;
    startTransition(async () => {
      try {
        const next = await fetchRadar({
          q: submitted || undefined,
          set: setName || undefined,
          rarity: rarity || undefined,
          min_price: parsePrice(minPrice),
          max_price: parsePrice(maxPrice),
          min_edge: minEdge,
          limit: 24,
        });
        setData(next);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("radar_error"));
      }
    });
  }, [
    user,
    status?.allowed,
    submitted,
    setName,
    rarity,
    minEdge,
    minPrice,
    maxPrice,
    t,
  ]);

  useEffect(() => {
    if (!hydrated || !status?.allowed) return;
    load();
  }, [hydrated, status?.allowed, load]);

  function onSearch(event: FormEvent) {
    event.preventDefault();
    setSubmitted(query.trim());
  }

  if (authLoading || !hydrated) {
    return (
      <section className="scanner-page radar-page">
        <p className="explore-lede">{t("radar_loading")}</p>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="scanner-page radar-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("radar_eyebrow")}</p>
          <h1 className="explore-title">{t("radar_title")}</h1>
          <p className="explore-lede">{t("radar_signin_lede")}</p>
        </div>
        <Link href="/portfolio" className="btn-primary">
          {t("auth_sign_in")}
        </Link>
      </section>
    );
  }

  if (status && !status.allowed) {
    return (
      <section className="scanner-page radar-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("radar_eyebrow")}</p>
          <h1 className="explore-title">{t("radar_locked")}</h1>
          <p className="explore-lede">{t("radar_locked_lede")}</p>
        </div>
        <div className="detail-actions">
          {status.checkout_url ? (
            <a href={status.checkout_url} className="btn-primary">
              {t("dealer_upgrade")}
            </a>
          ) : null}
          <Link href="/pro" className="btn-ghost">
            {t("dealer_pro_details")}
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="scanner-page radar-page">
      <div className="explore-command">
        <p className="explore-command-eyebrow">{t("radar_eyebrow")}</p>
        <h1 className="explore-title">{t("radar_title")}</h1>
        <p className="explore-lede">
          {t("radar_lede", { days: data.forecast_days || status?.forecast_days || 7 })}
          {data.source === "demo" ? ` · ${t("explore_demo")}` : ""}
        </p>
      </div>

      <form className="filter-bar scanner-search" onSubmit={onSearch}>
        <label className="sr-only" htmlFor="radar-q">
          {t("radar_search_aria")}
        </label>
        <input
          id="radar-q"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("radar_search_ph")}
        />
        <button type="submit" className="btn-primary">
          {t("radar_btn")}
        </button>
        <label>
          <span>{t("explore_set")}</span>
          <select value={setName} onChange={(e) => setSetName(e.target.value)}>
            <option value="">{t("explore_all_sets")}</option>
            {data.sets.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("scan_rarity")}</span>
          <select value={rarity} onChange={(e) => setRarity(e.target.value)}>
            <option value="">{t("explore_all")}</option>
            {data.rarities.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("radar_min_edge")}</span>
          <input
            type="number"
            min={0}
            max={100}
            step={0.5}
            value={minEdge}
            onChange={(e) => setMinEdge(Number(e.target.value) || 0)}
          />
        </label>
        <label>
          <span>{t("explore_min")}</span>
          <input
            value={minPrice}
            onChange={(e) => setMinPrice(e.target.value)}
            inputMode="decimal"
            placeholder={t("explore_any")}
          />
        </label>
        <label>
          <span>{t("explore_max")}</span>
          <input
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            inputMode="decimal"
            placeholder={t("explore_any")}
          />
        </label>
      </form>

      {error ? <p className="form-error">{error}</p> : null}
      {pending ? <p className="explore-lede">{t("explore_updating")}</p> : null}

      <div className="stat-row scanner-kpis">
        <div className="stat-chip">
          <span>{t("radar_kpi_sure")}</span>
          <strong>{data.sure_scoped}</strong>
        </div>
        <div className="stat-chip">
          <span>{t("radar_kpi_under")}</span>
          <strong>{data.under_total}</strong>
        </div>
        <div className="stat-chip">
          <span>{t("radar_kpi_over")}</span>
          <strong>{data.over_total}</strong>
        </div>
      </div>

      <h2 className="section-title">{t("radar_under_title")}</h2>
      {data.underpriced.length === 0 ? (
        <p className="explore-lede">{t("radar_under_empty")}</p>
      ) : (
        <div className="scan-list">
          {data.underpriced.map((card) => (
            <RadarRow key={`u-${card.id}`} card={card} />
          ))}
        </div>
      )}

      <h2 className="section-title">{t("radar_over_title")}</h2>
      {data.overpriced.length === 0 ? (
        <p className="explore-lede">{t("radar_over_empty")}</p>
      ) : (
        <div className="scan-list">
          {data.overpriced.map((card) => (
            <RadarRow key={`o-${card.id}`} card={card} />
          ))}
        </div>
      )}
    </section>
  );
}

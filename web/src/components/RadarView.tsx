"use client";

import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
  useTransition,
} from "react";

import { useAuth } from "@/components/AuthProvider";
import { useCurrency } from "@/components/CurrencyProvider";
import { DeskLoading } from "@/components/DeskLoading";
import { useLocale } from "@/components/LocaleProvider";
import { SearchSuggest } from "@/components/SearchSuggest";
import { TrustPanel } from "@/components/TrustPanel";
import {
  fetchRadar,
  fetchRadarBootstrap,
  formatChange,
} from "@/lib/api";
import {
  decisionOneLiner,
  sideLabel,
  sideTipKey,
} from "@/lib/i18n/messages";
import {
  buildRadarShareUrl,
  decodeRadarShare,
  type RadarShareFilters,
} from "@/lib/radarShare";
import { pushRecentSearch } from "@/lib/searchRecent";
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
  const { t, locale } = useLocale();
  const { formatSpot } = useCurrency();
  const band =
    card.pred_lo_pct != null && card.pred_hi_pct != null
      ? `${formatChange(card.pred_lo_pct, 1)}…${formatChange(card.pred_hi_pct, 1)}`
      : null;
  const edgeUp = (card.edge_pct ?? 0) >= 0;
  const verdict = decisionOneLiner(locale, card.side, card.edge_pct);
  const fair = formatSpot(card.fair_price ?? card.predicted_price);
  const edge = formatChange(card.edge_pct);
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
        <div className="radar-side" title={t(sideTipKey(card.side))}>
          {sideLabel(locale, card.side)}
        </div>
        <div className="lot-name">{card.name}</div>
        <div className="lot-meta">
          {[card.set_name, card.rarity].filter(Boolean).join(" · ")}
        </div>
        {verdict ? (
          <div className="decision-line lot-meta">{verdict}</div>
        ) : band ? (
          <div className="lot-meta" title={t("glossary_band_tip")}>
            {t("landing_dotd_band", { band })}
          </div>
        ) : null}
      </div>
      <div className="scan-metrics">
        <strong>{formatSpot(card.spot ?? card.price)}</strong>
        <span title={t("glossary_fair_tip")}>{t("metric_fair", { price: fair })}</span>
        <span className={edgeUp ? "pnl-up" : "pnl-down"} title={t("glossary_edge_tip")}>
          {t("metric_edge", { pct: edge })}
        </span>
      </div>
    </Link>
  );
}

export function RadarView() {
  const { t } = useLocale();
  const { user, loading: authLoading } = useAuth();
  const searchParams = useSearchParams();
  const shareBoot = useRef<RadarShareFilters | null | undefined>(undefined);
  const skipFilterLoad = useRef(false);
  const [booted, setBooted] = useState(false);
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
  const [shareNote, setShareNote] = useState<string | null>(null);
  const [shareBusy, setShareBusy] = useState(false);
  const [pending, startTransition] = useTransition();
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (shareBoot.current !== undefined) return;
    shareBoot.current = decodeRadarShare(searchParams.get("share"));
    const boot = shareBoot.current;
    if (!boot) return;
    if (boot.q) {
      setQuery(boot.q);
      setSubmitted(boot.q);
    }
    if (boot.set) setSetName(boot.set);
    if (boot.rarity) setRarity(boot.rarity);
    if (boot.min_edge != null) setMinEdge(boot.min_edge);
    if (boot.min_price != null) setMinPrice(String(boot.min_price));
    if (boot.max_price != null) setMaxPrice(String(boot.max_price));
  }, [searchParams]);

  const load = useCallback(
    (edgeOverride?: number) => {
      if (!user) return;
      const edge = edgeOverride ?? minEdge;
      startTransition(async () => {
        try {
          const next = await fetchRadar({
            q: submitted || undefined,
            set: setName || undefined,
            rarity: rarity || undefined,
            min_price: parsePrice(minPrice),
            max_price: parsePrice(maxPrice),
            min_edge: edge,
            limit: 24,
          });
          setData(next);
          setError(null);
        } catch (err) {
          setError(err instanceof Error ? err.message : t("radar_error"));
        } finally {
          setBooted(true);
        }
      });
    },
    [user, submitted, setName, rarity, minEdge, minPrice, maxPrice, t],
  );

  useEffect(() => {
    if (authLoading || !hydrated) return;
    if (!user) {
      setStatus(null);
      setData(EMPTY);
      setBooted(false);
      return;
    }
    startTransition(async () => {
      try {
        const boot = shareBoot.current;
        const edgeGuess = boot?.min_edge ?? minEdge;
        // One round-trip: Pro status + first board when allowed.
        const payload = await fetchRadarBootstrap({
          q: boot?.q || submitted || undefined,
          set: boot?.set || setName || undefined,
          rarity: boot?.rarity || rarity || undefined,
          min_price: boot?.min_price ?? parsePrice(minPrice),
          max_price: boot?.max_price ?? parsePrice(maxPrice),
          min_edge: edgeGuess,
          limit: 24,
        });
        setStatus(payload.status);
        if (boot?.min_edge == null) {
          setMinEdge(payload.status.edge_floor);
        }
        if (payload.status.allowed && payload.board) {
          setData(payload.board);
          skipFilterLoad.current = true;
        } else if (!payload.status.allowed) {
          setData(EMPTY);
        }
        setError(null);
      } catch (err) {
        setStatus(null);
        setError(err instanceof Error ? err.message : t("radar_error"));
      } finally {
        setBooted(true);
      }
    });
    // Initial boot only — filter changes go through `load`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, user, hydrated, t]);

  useEffect(() => {
    if (!hydrated || !status?.allowed || !user) return;
    if (skipFilterLoad.current) {
      skipFilterLoad.current = false;
      return;
    }
    load();
  }, [hydrated, status?.allowed, user, load]);

  function applyQuery(next: string) {
    const q = next.trim();
    setQuery(q);
    if (q) pushRecentSearch("radar", q);
    setSubmitted(q);
  }

  function onSearch(event: FormEvent) {
    event.preventDefault();
    applyQuery(query);
  }

  async function onShare() {
    if (!status?.allowed || shareBusy) return;
    setShareBusy(true);
    setShareNote(null);
    try {
      const url = buildRadarShareUrl(window.location.origin, {
        q: submitted || query || undefined,
        set: setName || undefined,
        rarity: rarity || undefined,
        min_edge: minEdge,
        min_price: parsePrice(minPrice),
        max_price: parsePrice(maxPrice),
      });
      await navigator.clipboard.writeText(`${t("radar_share_blurb")}\n${url}`);
      setShareNote(t("radar_share_copied"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("radar_share_error"));
    } finally {
      setShareBusy(false);
    }
  }

  if (authLoading || !hydrated || (user && !booted)) {
    return (
      <section className="scanner-page radar-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("radar_eyebrow")}</p>
          <h1 className="explore-title">{t("radar_title")}</h1>
        </div>
        <DeskLoading label={t("radar_loading")} variant="panel" skeletonCount={6} />
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
        <Link href="/portfolio?next=/radar" className="btn-primary">
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

      <form className="search-strip scanner-search" onSubmit={onSearch}>
        <SearchSuggest
          inputId="radar-q"
          value={query}
          onChange={setQuery}
          onCommit={applyQuery}
          placeholder={t("radar_search_ph")}
          ariaLabel={t("radar_search_aria")}
          recentScope="radar"
        />
        <button type="submit" className="btn-primary">
          {t("radar_btn")}
        </button>
        <button
          type="button"
          className="btn-ghost"
          disabled={shareBusy}
          onClick={() => void onShare()}
        >
          {shareBusy ? t("radar_share_busy") : t("radar_share_copy")}
        </button>
      </form>
      {shareNote ? <p className="pro-open-note">{shareNote}</p> : null}

      <div className="filter-row">
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
            type="number"
            min={0}
            step={1}
            value={minPrice}
            onChange={(e) => setMinPrice(e.target.value)}
            inputMode="decimal"
            placeholder={t("explore_any")}
          />
        </label>
        <label>
          <span>{t("explore_max")}</span>
          <input
            type="number"
            min={0}
            step={1}
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            inputMode="decimal"
            placeholder={t("explore_any")}
          />
        </label>
      </div>

      {error ? <p className="form-error">{error}</p> : null}
      {pending ? <DeskLoading label={t("explore_updating")} variant="banner" /> : null}

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
      {pending && data.underpriced.length === 0 ? (
        <DeskLoading label={t("explore_updating")} variant="panel" skeletonCount={4} />
      ) : data.underpriced.length === 0 ? (
        <p className="explore-lede">{t("radar_under_empty")}</p>
      ) : (
        <div className={`scan-list${pending ? " is-pending" : ""}`}>
          {data.underpriced.map((card) => (
            <RadarRow key={`u-${card.id}`} card={card} />
          ))}
        </div>
      )}

      <h2 className="section-title">{t("radar_over_title")}</h2>
      {pending && data.overpriced.length === 0 ? (
        <DeskLoading label={t("explore_updating")} variant="panel" skeletonCount={4} />
      ) : data.overpriced.length === 0 ? (
        <p className="explore-lede">{t("radar_over_empty")}</p>
      ) : (
        <div className={`scan-list${pending ? " is-pending" : ""}`}>
          {data.overpriced.map((card) => (
            <RadarRow key={`o-${card.id}`} card={card} />
          ))}
        </div>
      )}

      <TrustPanel />
    </section>
  );
}

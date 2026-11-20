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
import { RadarShareCard } from "@/components/RadarShareCard";
import { SearchSuggest } from "@/components/SearchSuggest";
import {
  fetchRadar,
  fetchRadarBootstrap,
  formatChange,
} from "@/lib/api";
import { onCardImageError, resolveCardImageUrl } from "@/lib/cardImage";
import { resolveDeskNumbers } from "@/lib/deskNumbers";
import {
  decisionOneLiner,
  sideLabel,
  sideTipKey,
} from "@/lib/i18n/messages";
import {
  downloadRadarSharePng,
  radarShareFilename,
} from "@/lib/radarExport";
import { SITE_URL } from "@/lib/seo";
import {
  buildRadarShareClipboardText,
  buildRadarShareUrl,
  decodeRadarShare,
  formatRadarShareFilters,
  type RadarShareFilters,
} from "@/lib/radarShare";
import { trackFunnel } from "@/lib/funnel";
import { pushRecentSearch } from "@/lib/searchRecent";
import type { RadarCard, RadarResponse, RadarStatus } from "@/lib/types";

function parsePrice(raw: string): number | undefined {
  const text = raw.trim();
  if (!text) return undefined;
  const n = Number(text);
  return Number.isFinite(n) && n >= 0 ? n : undefined;
}

function RadarSharePreview({ filters }: { filters: RadarShareFilters }) {
  const { t } = useLocale();
  const chips = formatRadarShareFilters(filters);
  return (
    <div className="radar-share-preview">
      <p className="explore-command-eyebrow">{t("radar_share_preview_title")}</p>
      <p className="explore-lede">{t("radar_share_preview_lede")}</p>
      {chips.length ? (
        <p className="radar-share-preview-chips">{chips.join(" · ")}</p>
      ) : (
        <p className="lot-meta">{t("radar_share_preview_empty")}</p>
      )}
    </div>
  );
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
  const desk = resolveDeskNumbers({
    spot: card.spot,
    price: card.price,
    fair_price: card.fair_price,
    predicted_price: card.predicted_price,
    side: card.side,
  });
  const verdict = decisionOneLiner(
    locale,
    desk.side || card.side,
    desk.edgeGapPct ?? card.edge_pct,
  );
  const fair = formatSpot(desk.good);
  return (
    <Link
      href={`/cards/${encodeURIComponent(card.id)}`}
      className="scan-row radar-row radar-under"
    >
      <div className="scan-art">
        <Image
          src={resolveCardImageUrl(card.id, card.image_url)}
          alt={card.name}
          width={48}
          height={67}
          onError={(event) => onCardImageError(event, card.id)}
        />
      </div>
      <div>
        <div className="lot-name">{card.name}</div>
        <div className="lot-meta">
          {[card.set_name, card.rarity].filter(Boolean).join(" · ")}
        </div>
        {verdict ? (
          <div className="decision-line lot-meta">{verdict}</div>
        ) : (
          <div className="lot-meta" title={t(sideTipKey(card.side))}>
            {sideLabel(locale, card.side)}
          </div>
        )}
      </div>
      <div className="scan-metrics">
        <strong>
          {t("metric_spot", { price: formatSpot(desk.asking) })}
        </strong>
        <span title={t("glossary_fair_tip")}>
          {t("metric_fair", { price: fair })}
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
  const [exportBusy, setExportBusy] = useState(false);
  const [exportNote, setExportNote] = useState<string | null>(null);
  const [sharedFilters, setSharedFilters] = useState<RadarShareFilters | null>(
    null,
  );
  const shareCardRef = useRef<HTMLDivElement>(null);
  const [pending, startTransition] = useTransition();
  const [hydrated, setHydrated] = useState(false);
  const { formatSpot } = useCurrency();

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (shareBoot.current !== undefined) return;
    shareBoot.current = decodeRadarShare(searchParams.get("share"));
    const boot = shareBoot.current;
    setSharedFilters(boot);
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

  useEffect(() => {
    if (!status?.allowed) return;
    trackFunnel("radar_activate", { source: data.source }, { once: true });
  }, [status?.allowed, data.source]);

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

  function currentShareFilters(): RadarShareFilters {
    return {
      q: submitted || query || undefined,
      set: setName || undefined,
      rarity: rarity || undefined,
      min_edge: minEdge,
      min_price: parsePrice(minPrice),
      max_price: parsePrice(maxPrice),
    };
  }

  async function onShare() {
    if (!status?.allowed || shareBusy) return;
    setShareBusy(true);
    setShareNote(null);
    setExportNote(null);
    setError(null);
    try {
      const filters = currentShareFilters();
      const url = buildRadarShareUrl(SITE_URL, filters);
      const top = data.underpriced[0];
      const topDesk = top
        ? resolveDeskNumbers({
            spot: top.spot,
            price: top.price,
            fair_price: top.fair_price,
            predicted_price: top.predicted_price,
            side: top.side,
          })
        : null;
      const text = buildRadarShareClipboardText({
        blurb: t("radar_share_blurb"),
        filters,
        board: {
          underTotal: data.under_total,
          overTotal: data.over_total,
          topUnderName: top?.name,
          topUnderEdgePct: topDesk?.edgeGapPct ?? top?.edge_pct,
        },
        url,
        filtersLabel: t("radar_share_filters"),
        boardLine: (under, _over) =>
          t("radar_share_board", { under, over: 0 }),
        topUnderLine: (name, edge) =>
          t("radar_share_top_under", { name, edge }),
      });
      try {
        await navigator.clipboard.writeText(text);
        setShareNote(t("radar_share_copied"));
        trackFunnel("share_copy", { surface: "radar" });
      } catch {
        setShareNote(`${t("radar_share_copied_fallback")}\n${url}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("radar_share_error"));
    } finally {
      setShareBusy(false);
    }
  }

  async function onExportPng() {
    if (!status?.allowed || exportBusy || !shareCardRef.current) return;
    setExportBusy(true);
    setExportNote(null);
    setShareNote(null);
    setError(null);
    try {
      const { copied } = await downloadRadarSharePng(
        shareCardRef.current,
        radarShareFilename(),
      );
      trackFunnel("share_png", {
        surface: "radar",
        clipboard: copied,
        under: data.under_total,
        over: data.over_total,
      });
      setExportNote(
        copied ? t("radar_export_done_clipboard") : t("radar_export_done"),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : t("radar_export_error"));
    } finally {
      setExportBusy(false);
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
        {sharedFilters ? <RadarSharePreview filters={sharedFilters} /> : null}
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
        {sharedFilters ? <RadarSharePreview filters={sharedFilters} /> : null}
        <div className="detail-actions">
          {status.checkout_url ? (
            <a
              href={status.checkout_url}
              className="btn-primary"
              onClick={() =>
                trackFunnel("pro_checkout_click", { source: "radar_gate" })
              }
            >
              {t("dealer_upgrade")}
            </a>
          ) : null}
          <Link
            href="/pro"
            className="btn-ghost"
            onClick={() =>
              trackFunnel("landing_cta_pro", { source: "radar_gate" })
            }
          >
            {t("dealer_pro_details")}
          </Link>
        </div>
      </section>
    );
  }

  const shareFilters = currentShareFilters();
  const topUnder = data.underpriced[0] ?? null;
  const topUnderDesk = topUnder
    ? resolveDeskNumbers({
        spot: topUnder.spot,
        price: topUnder.price,
        fair_price: topUnder.fair_price,
        predicted_price: topUnder.predicted_price,
        side: topUnder.side,
      })
    : null;
  // Canonical origin on SSR + first client paint (avoid typeof window → #418).
  const shareUrl = buildRadarShareUrl(SITE_URL, shareFilters);

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

      <div className="detail-actions">
        <button
          type="button"
          className="btn-ghost"
          disabled={shareBusy || exportBusy}
          onClick={() => void onShare()}
        >
          {shareBusy ? t("radar_share_busy") : t("radar_share_copy")}
        </button>
        <button
          type="button"
          className="btn-ghost"
          disabled={exportBusy || shareBusy}
          onClick={() => void onExportPng()}
        >
          {exportBusy ? t("radar_export_busy") : t("radar_export_image")}
        </button>
      </div>
      <p className="lot-meta">{t("radar_share_hint")}</p>
      {shareNote ? <p className="pro-open-note">{shareNote}</p> : null}
      {exportNote ? <p className="pro-open-note">{exportNote}</p> : null}

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
      </form>

      <div className="filter-row">
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
        </div>
      </details>

      {error ? <p className="form-error">{error}</p> : null}
      {pending ? <DeskLoading label={t("explore_updating")} variant="banner" /> : null}

      <div className="kpi-row scanner-kpis">
        <div className="kpi-chip">
          <span>{t("radar_kpi_sure")}</span>
          <strong>{data.sure_scoped}</strong>
        </div>
        <div className="kpi-chip">
          <span>{t("radar_kpi_under")}</span>
          <strong>{data.under_total}</strong>
        </div>
      </div>

      <div className="portfolio-section-head">
        <h2>{t("radar_under_title")}</h2>
      </div>
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

      <div className="trade-share-card-host" aria-hidden="true">
        <RadarShareCard
          ref={shareCardRef}
          filters={shareFilters}
          underTotal={data.under_total}
          overTotal={data.over_total}
          topUnder={topUnder}
          spotLabel={
            topUnderDesk ? formatSpot(topUnderDesk.asking) : "—"
          }
          fairLabel={
            topUnderDesk ? formatSpot(topUnderDesk.good) : "—"
          }
          edgeLabel={
            topUnderDesk ? formatChange(topUnderDesk.edgeGapPct) : "—"
          }
          shareUrl={shareUrl}
        />
      </div>
    </section>
  );
}

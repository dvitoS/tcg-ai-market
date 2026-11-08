"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useLocale } from "@/components/LocaleProvider";
import { SearchSuggest } from "@/components/SearchSuggest";
import { TradeReportExport } from "@/components/TradeReportExport";
import {
  createTradeShare,
  fetchCardDetail,
  fetchCatalog,
  fetchTradeStatus,
  formatChange,
  formatMoney,
  scoreTrade,
} from "@/lib/api";
import { trackFunnel } from "@/lib/funnel";
import { pushRecentSearch } from "@/lib/searchRecent";
import type {
  CatalogCard,
  TradeLineIn,
  TradeResponse,
  TradeSide,
  TradeStatus,
} from "@/lib/types";
import {
  PRINTINGS,
  RAW_CONDITIONS,
  normalizeCondition,
  normalizePrinting,
} from "@/lib/lotPriceAdjust";

type SideKey = "you" | "them";

/** Local draft — preview art/name stay client-side until Score fills TradeSide. */
type TradeLineDraft = TradeLineIn & {
  name?: string | null;
  set_name?: string | null;
  image_url?: string | null;
};

function lineKey(
  line: Pick<TradeLineIn, "card_id" | "condition" | "printing">,
): string {
  return `${line.card_id}|${normalizeCondition(line.condition)}|${normalizePrinting(line.printing)}`;
}

function toTradePayload(lines: TradeLineDraft[]): TradeLineIn[] {
  return lines.map((line) => ({
    card_id: line.card_id,
    quantity: line.quantity,
    condition: normalizeCondition(line.condition),
    printing: normalizePrinting(line.printing),
  }));
}

function previewFromCard(card: CatalogCard): Pick<
  TradeLineDraft,
  "name" | "set_name" | "image_url"
> {
  return {
    name: card.name,
    set_name: card.set_name,
    image_url: card.image_url,
  };
}

function verdictClass(verdict: string): string {
  if (verdict === "YOU_AHEAD") return "trade-you";
  if (verdict === "THEM_AHEAD") return "trade-them";
  return "trade-fair";
}

function verdictLabelKey(
  verdict: string,
): "trade_v_you_ahead" | "trade_v_them_ahead" | "trade_v_fair" {
  if (verdict === "YOU_AHEAD") return "trade_v_you_ahead";
  if (verdict === "THEM_AHEAD") return "trade_v_them_ahead";
  return "trade_v_fair";
}

function SidePanel({
  title,
  side,
  lines,
  onRemove,
  onPatch,
}: {
  title: string;
  side: TradeSide | null;
  lines: TradeLineDraft[];
  onRemove: (line: TradeLineDraft) => void;
  onPatch: (
    line: TradeLineDraft,
    patch: Partial<Pick<TradeLineIn, "condition" | "printing">>,
  ) => void;
}) {
  const { t } = useLocale();
  return (
    <div className="trade-side">
      <div className="trade-side-head">
        <h2>{title}</h2>
        {side ? (
          <p className="lot-meta">
            {t("trade_side_totals", {
              spot: formatMoney(side.spot_total),
              fair: formatMoney(side.fair_total),
            })}
          </p>
        ) : (
          <p className="lot-meta">{t("trade_side_empty")}</p>
        )}
      </div>
      <div className="trade-lines">
        {lines.length === 0 ? (
          <p className="explore-lede">{t("trade_add_hint")}</p>
        ) : (
          lines.map((line) => {
            const scored = side?.lines.find(
              (r) =>
                r.card_id === line.card_id &&
                normalizeCondition(r.condition) === normalizeCondition(line.condition) &&
                normalizePrinting(r.printing) === normalizePrinting(line.printing),
            );
            const name = scored?.name || line.name || line.card_id;
            const image = scored?.image_url || line.image_url || "/kestrel-logo.png";
            const setName = scored?.set_name || line.set_name;
            return (
              <div key={lineKey(line)} className="trade-line">
                <div className="scan-art">
                  <Image
                    src={image}
                    alt={name}
                    width={40}
                    height={56}
                  />
                </div>
                <div>
                  <div className="lot-name">{name}</div>
                  <div className="lot-meta">
                    ×{line.quantity}
                    {setName ? ` · ${setName}` : ""}
                    {scored?.spot != null ? ` · ${formatMoney(scored.spot)}` : ""}
                    {scored?.spot_source === "justtcg_variant"
                      ? ` · ${t("port_spot_live")}`
                      : scored?.spot_source === "multiplier"
                        ? ` · ${t("port_spot_estimated")}`
                        : ""}
                    {scored?.expected_change_pct != null
                      ? ` · AI ${formatChange(scored.expected_change_pct)}`
                      : ""}
                  </div>
                  <div className="trade-line-meta">
                    <select
                      aria-label={t("port_condition")}
                      value={normalizeCondition(line.condition)}
                      onChange={(e) =>
                        onPatch(line, { condition: e.target.value })
                      }
                    >
                      {RAW_CONDITIONS.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                    <select
                      aria-label={t("port_printing")}
                      value={normalizePrinting(line.printing)}
                      onChange={(e) =>
                        onPatch(line, { printing: e.target.value })
                      }
                    >
                      {PRINTINGS.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn-ghost trade-remove"
                  onClick={() => onRemove(line)}
                >
                  {t("trade_remove")}
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export function TradeView() {
  const { t } = useLocale();
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const seededRef = useRef(false);
  const [status, setStatus] = useState<TradeStatus | null>(null);
  const [statusReady, setStatusReady] = useState(false);
  const [you, setYou] = useState<TradeLineDraft[]>([]);
  const [them, setThem] = useState<TradeLineDraft[]>([]);
  const [result, setResult] = useState<TradeResponse | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<CatalogCard[]>([]);
  const [searchedFor, setSearchedFor] = useState<string | null>(null);
  const [target, setTarget] = useState<SideKey>("you");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [searching, setSearching] = useState(false);
  const [shareBusy, setShareBusy] = useState(false);
  const [shareNote, setShareNote] = useState<string | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [seedNote, setSeedNote] = useState<string | null>(null);

  useEffect(() => {
    if (seededRef.current) return;
    const raw = (searchParams.get("add") || "").trim();
    if (!raw) return;
    seededRef.current = true;
    const side: SideKey = searchParams.get("side") === "them" ? "them" : "you";
    const ids = raw
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean)
      .slice(0, 12);
    if (ids.length === 0) return;
    setTarget(side);
    const setter = side === "you" ? setYou : setThem;
    setter((prev) => {
      const qty = new Map(prev.map((r) => [lineKey(r), r]));
      for (const cardId of ids) {
        const key = lineKey({
          card_id: cardId,
          condition: "NM",
          printing: "Normal",
        });
        const existing = qty.get(key);
        if (existing) {
          qty.set(key, { ...existing, quantity: existing.quantity + 1 });
        } else {
          qty.set(key, {
            card_id: cardId,
            quantity: 1,
            condition: "NM",
            printing: "Normal",
          });
        }
      }
      return Array.from(qty.values());
    });
    setSeedNote(
      t(side === "you" ? "trade_seed_you" : "trade_seed_them", { n: ids.length }),
    );
    // Hydrate name + art for deeplinked ids (payload only has card_id).
    void Promise.all(
      ids.map(async (cardId) => {
        try {
          const detail = await fetchCardDetail(cardId);
          const preview = previewFromCard(detail.card);
          const apply = (prev: TradeLineDraft[]) =>
            prev.map((line) =>
              line.card_id === cardId && !line.image_url && !line.name
                ? { ...line, ...preview }
                : line,
            );
          if (side === "you") setYou(apply);
          else setThem(apply);
        } catch {
          /* keep id-only line */
        }
      }),
    );
    router.replace("/trade", { scroll: false });
  }, [searchParams, router, t]);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      setStatus(null);
      setStatusReady(true);
      return;
    }
    setStatusReady(false);
    void fetchTradeStatus()
      .then((st) => {
        setStatus(st);
        setError(null);
      })
      .catch((err) => {
        setStatus(null);
        setError(err instanceof Error ? err.message : t("trade_error"));
      })
      .finally(() => {
        setStatusReady(true);
      });
  }, [authLoading, user, t]);

  useEffect(() => {
    if (!status?.allowed) return;
    trackFunnel("trade_activate", undefined, { once: true });
  }, [status?.allowed]);

  function addCard(card: CatalogCard) {
    const preview = previewFromCard(card);
    const setter = target === "you" ? setYou : setThem;
    setter((prev) => {
      const existing = prev.find(
        (r) =>
          r.card_id === card.id &&
          normalizeCondition(r.condition) === "NM" &&
          normalizePrinting(r.printing) === "Normal",
      );
      if (existing) {
        return prev.map((r) =>
          r.card_id === card.id &&
          normalizeCondition(r.condition) === "NM" &&
          normalizePrinting(r.printing) === "Normal"
            ? { ...r, ...preview, quantity: r.quantity + 1 }
            : r,
        );
      }
      return [
        ...prev,
        {
          card_id: card.id,
          quantity: 1,
          condition: "NM",
          printing: "Normal",
          ...preview,
        },
      ];
    });
    setResult(null);
    setShareNote(null);
    setHits((prev) => prev.filter((h) => h.id !== card.id));
    setQuery("");
  }

  function patchLine(
    side: SideKey,
    line: TradeLineDraft,
    patch: Partial<Pick<TradeLineIn, "condition" | "printing">>,
  ) {
    const setter = side === "you" ? setYou : setThem;
    const fromKey = lineKey(line);
    setter((prev) => {
      const nextCond = patch.condition
        ? normalizeCondition(patch.condition)
        : normalizeCondition(line.condition);
      const nextPrint = patch.printing
        ? normalizePrinting(patch.printing)
        : normalizePrinting(line.printing);
      const nextKey = lineKey({
        card_id: line.card_id,
        condition: nextCond,
        printing: nextPrint,
      });
      const without = prev.filter((r) => lineKey(r) !== fromKey);
      const collide = without.find((r) => lineKey(r) === nextKey);
      if (collide) {
        return without.map((r) =>
          lineKey(r) === nextKey
            ? { ...r, quantity: r.quantity + line.quantity }
            : r,
        );
      }
      return without.concat([
        {
          ...line,
          condition: nextCond,
          printing: nextPrint,
        },
      ]);
    });
    setResult(null);
    setShareNote(null);
  }

  async function runSearch(raw: string) {
    const q = raw.trim();
    if (!q) {
      setHits([]);
      setSearchedFor(null);
      return;
    }
    pushRecentSearch("trade", q);
    setSearching(true);
    setError(null);
    setSearchedFor(q);
    try {
      const catalog = await fetchCatalog({ q, limit: 8, mode: "browse" });
      setHits(catalog.items || []);
    } catch (err) {
      setHits([]);
      setError(err instanceof Error ? err.message : t("trade_error"));
    } finally {
      setSearching(false);
    }
  }

  function onSearch(event: FormEvent) {
    event.preventDefault();
    void runSearch(query);
  }

  function removeFrom(side: SideKey, line: TradeLineDraft) {
    const setter = side === "you" ? setYou : setThem;
    const key = lineKey(line);
    setter((prev) => prev.filter((r) => lineKey(r) !== key));
    setResult(null);
  }

  async function onScore() {
    if (!user || !status?.allowed) return;
    setBusy(true);
    setError(null);
    setShareNote(null);
    try {
      const scored = await scoreTrade({
        you: toTradePayload(you),
        them: toTradePayload(them),
      });
      setResult(scored);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : t("trade_error"));
    } finally {
      setBusy(false);
    }
  }

  async function ensureShareUrl(): Promise<string | null> {
    if (!user || !status?.allowed || (you.length === 0 && them.length === 0)) {
      return null;
    }
    const created = await createTradeShare({
      you: toTradePayload(you),
      them: toTradePayload(them),
    });
    const href =
      created.url ||
      `${typeof window !== "undefined" ? window.location.origin : ""}${created.path}`;
    setShareUrl(href);
    return href;
  }

  async function onShare() {
    if (!user || !status?.allowed || (you.length === 0 && them.length === 0)) {
      return;
    }
    setShareBusy(true);
    setShareNote(null);
    setError(null);
    try {
      const href = await ensureShareUrl();
      if (!href) return;
      try {
        await navigator.clipboard.writeText(href);
        setShareNote(t("trade_share_copied"));
      } catch {
        setShareNote(href);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("trade_share_error"));
    } finally {
      setShareBusy(false);
    }
  }

  if (authLoading || (user && !statusReady)) {
    return (
      <section className="scanner-page trade-page">
        <p className="explore-lede">{t("trade_loading")}</p>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="scanner-page trade-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("trade_eyebrow")}</p>
          <h1 className="explore-title">{t("trade_title")}</h1>
          <p className="explore-lede">{t("trade_signin_lede")}</p>
        </div>
        <Link href="/portfolio?next=/trade" className="btn-primary">
          {t("auth_sign_in")}
        </Link>
      </section>
    );
  }

  if (error && !status) {
    return (
      <section className="scanner-page trade-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("trade_eyebrow")}</p>
          <h1 className="explore-title">{t("trade_title")}</h1>
          <p className="form-error">{error}</p>
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => {
            setStatusReady(false);
            setError(null);
            void fetchTradeStatus()
              .then((st) => {
                setStatus(st);
                setError(null);
              })
              .catch((err) => {
                setStatus(null);
                setError(err instanceof Error ? err.message : t("trade_error"));
              })
              .finally(() => setStatusReady(true));
          }}
        >
          {t("port_refresh")}
        </button>
      </section>
    );
  }

  if (status && !status.allowed) {
    return (
      <section className="scanner-page trade-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("trade_eyebrow")}</p>
          <h1 className="explore-title">{t("trade_locked")}</h1>
          <p className="explore-lede">{t("trade_locked_lede")}</p>
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
    <section className="scanner-page trade-page">
      <div className="explore-command">
        <p className="explore-command-eyebrow">{t("trade_eyebrow")}</p>
        <h1 className="explore-title">{t("trade_title")}</h1>
        <p className="explore-lede">{t("trade_lede")}</p>
        {seedNote ? <p className="pro-open-note">{seedNote}</p> : null}
      </div>

      <div className="trade-target">
        <span>{t("trade_add_to")}</span>
        <button
          type="button"
          className={`btn-ghost ${target === "you" ? "is-active" : ""}`}
          onClick={() => setTarget("you")}
        >
          {t("trade_you")}
        </button>
        <button
          type="button"
          className={`btn-ghost ${target === "them" ? "is-active" : ""}`}
          onClick={() => setTarget("them")}
        >
          {t("trade_them")}
        </button>
      </div>

      <form className="search-strip scanner-search" onSubmit={onSearch}>
        <SearchSuggest
          value={query}
          onChange={setQuery}
          onCommit={(q) => {
            setQuery(q);
            void runSearch(q);
          }}
          onPickCard={addCard}
          placeholder={t("trade_search_ph")}
          ariaLabel={t("trade_search_aria")}
          recentScope="trade"
        />
        <button type="submit" className="btn-primary" disabled={searching}>
          {searching ? t("search_loading") : t("trade_search_btn")}
        </button>
      </form>

      {hits.length > 0 ? (
        <div className="trade-hits">
          {hits.map((card) => (
            <button
              key={card.id}
              type="button"
              className="trade-hit"
              onClick={() => addCard(card)}
            >
              <span className="lot-name">{card.name}</span>
              <span className="lot-meta">
                {[card.set_name, formatMoney(card.price)].filter(Boolean).join(" · ")}
              </span>
            </button>
          ))}
        </div>
      ) : searching ? (
        <p className="lot-meta">{t("search_loading")}</p>
      ) : searchedFor &&
        searchedFor === query.trim() &&
        hits.length === 0 ? (
        <p className="lot-meta">{t("search_no_hits")}</p>
      ) : null}

      <div className="trade-board">
        <SidePanel
          title={t("trade_you_give")}
          side={result?.you ?? null}
          lines={you}
          onRemove={(line) => removeFrom("you", line)}
          onPatch={(line, patch) => patchLine("you", line, patch)}
        />
        <SidePanel
          title={t("trade_them_give")}
          side={result?.them ?? null}
          lines={them}
          onRemove={(line) => removeFrom("them", line)}
          onPatch={(line, patch) => patchLine("them", line, patch)}
        />
      </div>

      <div className="detail-actions">
        <button
          type="button"
          className="btn-primary"
          disabled={
            busy || !status?.allowed || (you.length === 0 && them.length === 0)
          }
          onClick={() => void onScore()}
        >
          {busy ? t("trade_scoring") : t("trade_score")}
        </button>
        <button
          type="button"
          className="btn-ghost"
          disabled={
            shareBusy ||
            busy ||
            !status?.allowed ||
            (you.length === 0 && them.length === 0)
          }
          onClick={() => void onShare()}
        >
          {shareBusy ? t("trade_share_busy") : t("trade_share_copy")}
        </button>
        <button
          type="button"
          className="btn-ghost"
          onClick={() => {
            setYou([]);
            setThem([]);
            setResult(null);
            setQuery("");
            setHits([]);
            setSearchedFor(null);
            setShareNote(null);
            setShareUrl(null);
          }}
        >
          {t("trade_clear")}
        </button>
      </div>

      {error ? <p className="form-error">{error}</p> : null}
      {shareNote ? <p className="pro-open-note">{shareNote}</p> : null}

      {result ? (
        <>
          <div className={`trade-verdict ${verdictClass(result.verdict)}`}>
            <p className="trade-verdict-label">{t("trade_verdict")}</p>
            <h2>{t(verdictLabelKey(result.verdict))}</h2>
            <p className="explore-lede">
              {t("trade_net_spot", {
                value: formatMoney(result.net_spot_usd),
                pct: formatChange(result.net_spot_pct),
              })}
            </p>
            <p className="explore-lede">
              {t("trade_net_ai", {
                value: formatMoney(result.net_fair_usd),
                pct: formatChange(result.net_fair_pct),
              })}
            </p>
            <p className="lot-meta">
              {t("trade_band_note", { n: result.fair_band_pct })}
              {result.source === "demo" ? ` · ${t("explore_demo")}` : ""}
            </p>
          </div>
          <TradeReportExport
            trade={result}
            shareUrl={shareUrl}
            onEnsureShare={
              status?.allowed
                ? async () => {
                    try {
                      return await ensureShareUrl();
                    } catch (err) {
                      setError(
                        err instanceof Error
                          ? err.message
                          : t("trade_share_error"),
                      );
                      return null;
                    }
                  }
                : undefined
            }
          />
        </>
      ) : null}
    </section>
  );
}

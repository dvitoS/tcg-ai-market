"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useLocale } from "@/components/LocaleProvider";
import { SearchSuggest } from "@/components/SearchSuggest";
import {
  fetchTradeStatus,
  formatChange,
  formatMoney,
  scoreTrade,
} from "@/lib/api";
import { pushRecentSearch } from "@/lib/searchRecent";
import type {
  CatalogCard,
  TradeLineIn,
  TradeResponse,
  TradeSide,
  TradeStatus,
} from "@/lib/types";

type SideKey = "you" | "them";

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
}: {
  title: string;
  side: TradeSide | null;
  lines: TradeLineIn[];
  onRemove: (cardId: string) => void;
}) {
  const { t } = useLocale();
  return (
    <div className="trade-side">
      <div className="trade-side-head">
        <h2>{title}</h2>
        {side ? (
          <p className="lot-meta">
            {formatMoney(side.spot_total)} spot · {formatMoney(side.fair_total)} AI
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
            const scored = side?.lines.find((r) => r.card_id === line.card_id);
            return (
              <div key={line.card_id} className="trade-line">
                <div className="scan-art">
                  <Image
                    src={scored?.image_url || "/kestrel-logo.png"}
                    alt={scored?.name || line.card_id}
                    width={40}
                    height={56}
                  />
                </div>
                <div>
                  <div className="lot-name">{scored?.name || line.card_id}</div>
                  <div className="lot-meta">
                    ×{line.quantity}
                    {scored?.spot != null ? ` · ${formatMoney(scored.spot)}` : ""}
                    {scored?.expected_change_pct != null
                      ? ` · AI ${formatChange(scored.expected_change_pct)}`
                      : ""}
                  </div>
                </div>
                <button
                  type="button"
                  className="btn-ghost trade-remove"
                  onClick={() => onRemove(line.card_id)}
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
  const [you, setYou] = useState<TradeLineIn[]>([]);
  const [them, setThem] = useState<TradeLineIn[]>([]);
  const [result, setResult] = useState<TradeResponse | null>(null);
  const [query, setQuery] = useState("");
  const [target, setTarget] = useState<SideKey>("you");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
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
      const qty = new Map(prev.map((r) => [r.card_id, r.quantity]));
      for (const cardId of ids) {
        qty.set(cardId, (qty.get(cardId) || 0) + 1);
      }
      return Array.from(qty.entries()).map(([card_id, quantity]) => ({
        card_id,
        quantity,
      }));
    });
    setSeedNote(
      t(side === "you" ? "trade_seed_you" : "trade_seed_them", { n: ids.length }),
    );
    router.replace("/trade", { scroll: false });
  }, [searchParams, router, t]);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      setStatus(null);
      return;
    }
    void fetchTradeStatus()
      .then((st) => {
        setStatus(st);
        setError(null);
      })
      .catch((err) => {
        setStatus(null);
        setError(err instanceof Error ? err.message : t("trade_error"));
      });
  }, [authLoading, user, t]);

  function addCard(card: CatalogCard) {
    const setter = target === "you" ? setYou : setThem;
    setter((prev) => {
      const existing = prev.find((r) => r.card_id === card.id);
      if (existing) {
        return prev.map((r) =>
          r.card_id === card.id ? { ...r, quantity: r.quantity + 1 } : r,
        );
      }
      return [...prev, { card_id: card.id, quantity: 1 }];
    });
    setResult(null);
    setQuery("");
  }

  function onSearch(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    if (q) pushRecentSearch("trade", q);
  }

  function removeFrom(side: SideKey, cardId: string) {
    const setter = side === "you" ? setYou : setThem;
    setter((prev) => prev.filter((r) => r.card_id !== cardId));
    setResult(null);
  }

  async function onScore() {
    if (!user || !status?.allowed) return;
    setBusy(true);
    setError(null);
    try {
      const scored = await scoreTrade({ you, them });
      setResult(scored);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : t("trade_error"));
    } finally {
      setBusy(false);
    }
  }

  if (authLoading) {
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
        <Link href="/portfolio" className="btn-primary">
          {t("auth_sign_in")}
        </Link>
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
            if (q) pushRecentSearch("trade", q);
          }}
          onPickCard={addCard}
          placeholder={t("trade_search_ph")}
          ariaLabel={t("trade_search_aria")}
          recentScope="trade"
        />
        <button type="submit" className="btn-primary">
          {t("trade_search_btn")}
        </button>
      </form>

      <div className="trade-board">
        <SidePanel
          title={t("trade_you_give")}
          side={result?.you ?? null}
          lines={you}
          onRemove={(id) => removeFrom("you", id)}
        />
        <SidePanel
          title={t("trade_them_give")}
          side={result?.them ?? null}
          lines={them}
          onRemove={(id) => removeFrom("them", id)}
        />
      </div>

      <div className="detail-actions">
        <button
          type="button"
          className="btn-primary"
          disabled={busy || (you.length === 0 && them.length === 0)}
          onClick={() => void onScore()}
        >
          {busy ? t("trade_scoring") : t("trade_score")}
        </button>
        <button
          type="button"
          className="btn-ghost"
          onClick={() => {
            setYou([]);
            setThem([]);
            setResult(null);
            setQuery("");
          }}
        >
          {t("trade_clear")}
        </button>
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      {result ? (
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
      ) : null}
    </section>
  );
}

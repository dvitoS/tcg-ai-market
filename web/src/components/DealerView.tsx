"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useLocale } from "@/components/LocaleProvider";
import {
  fetchDealerStatus,
  formatChange,
  formatMoney,
  scoreDealerCsv,
} from "@/lib/api";
import { downloadDealerCsv } from "@/lib/dealerCsv";
import {
  clearDealerSync,
  readDealerSync,
  writeDealerSync,
} from "@/lib/dealerSync";
import type { DealerResponse, DealerRow, DealerStatus } from "@/lib/types";

function actionClass(action: string): string {
  if (action === "BUY_MORE") return "action-buy";
  if (action === "LIST") return "action-list";
  return "action-hold";
}

function ActionRow({ row }: { row: DealerRow }) {
  const band =
    row.pred_lo_pct != null && row.pred_hi_pct != null
      ? ` · PI ${formatChange(row.pred_lo_pct)}…${formatChange(row.pred_hi_pct)}`
      : "";
  return (
    <div className={`dealer-row ${actionClass(row.action)}`}>
      <div>
        <div className="dealer-action">{row.action.replace("_", " ")}</div>
        <Link
          href={row.card_id ? `/cards/${encodeURIComponent(row.card_id)}` : "/dealer"}
          className="lot-name"
        >
          {row.name || row.card_id || "Unknown"}
        </Link>
        <p className="lot-meta">
          qty {row.quantity}
          {row.card_id ? ` · ${row.card_id}` : ""}
          {row.set_name ? ` · ${row.set_name}` : ""}
        </p>
      </div>
      <div className="dealer-metrics">
        <strong>{formatMoney(row.spot)}</strong>
        <span>AI {formatChange(row.expected_change_pct)}</span>
        <span>
          net edge {formatChange(row.net_edge_pct)}
          {band}
        </span>
      </div>
    </div>
  );
}

export function DealerView() {
  const { t } = useLocale();
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<DealerStatus | null>(null);
  const [csvText, setCsvText] = useState("");
  const [fee, setFee] = useState(13);
  const [ship, setShip] = useState(4);
  const [result, setResult] = useState<DealerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [syncedAt, setSyncedAt] = useState<string | null>(null);
  const [autoScore, setAutoScore] = useState(true);
  const autoScoredRef = useRef(false);

  const userId = user?.id || user?.email || null;

  const runScore = useCallback(
    async (text: string, feePct: number, shipUsd: number) => {
      if (!user || !text.trim()) return;
      setBusy(true);
      setError(null);
      try {
        const scored = await scoreDealerCsv({
          csv_text: text,
          fee_pct: feePct,
          ship_usd: shipUsd,
        });
        setResult(scored);
        writeDealerSync(userId, {
          csvText: text,
          feePct,
          shipUsd,
          format: scored.inventory_format,
        });
        setSyncedAt(new Date().toISOString());
      } catch (err) {
        setResult(null);
        setError(err instanceof Error ? err.message : "Score failed");
      } finally {
        setBusy(false);
      }
    },
    [user, userId],
  );

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      setStatus(null);
      return;
    }
    async function boot() {
      try {
        const st = await fetchDealerStatus();
        setStatus(st);
        setFee(st.default_fee_pct);
        setShip(st.default_ship_usd);
        const saved = readDealerSync(userId);
        if (saved?.csvText) {
          setCsvText(saved.csvText);
          setFee(saved.feePct ?? st.default_fee_pct);
          setShip(saved.shipUsd ?? st.default_ship_usd);
          setSyncedAt(saved.savedAt || null);
        } else {
          setCsvText(st.sample_csv);
          setSyncedAt(null);
        }
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Dealer unavailable");
      }
    }
    void boot();
  }, [authLoading, user, userId]);

  useEffect(() => {
    if (!status?.allowed || !autoScore || !csvText.trim() || !syncedAt) return;
    if (autoScoredRef.current) return;
    autoScoredRef.current = true;
    void runScore(csvText, fee, ship);
  }, [status?.allowed, autoScore, csvText, fee, ship, syncedAt, runScore]);

  async function onScore(event: FormEvent) {
    event.preventDefault();
    await runScore(csvText, fee, ship);
  }

  function onFile(file: File | null) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || "");
      setCsvText(text);
      writeDealerSync(userId, {
        csvText: text,
        feePct: fee,
        shipUsd: ship,
      });
      setSyncedAt(new Date().toISOString());
      autoScoredRef.current = false;
    };
    reader.readAsText(file);
  }

  function onClearSync() {
    clearDealerSync(userId);
    setSyncedAt(null);
    setResult(null);
    if (status?.sample_csv) setCsvText(status.sample_csv);
    autoScoredRef.current = false;
  }

  const actionable =
    result?.items.filter((row) => row.action === "LIST" || row.action === "BUY_MORE") ||
    [];

  if (!authLoading && !user) {
    return (
      <section className="dealer-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("dealer_eyebrow")}</p>
          <h1 className="explore-title">{t("dealer_title")}</h1>
          <p className="explore-lede">{t("dealer_signin_lede")}</p>
        </div>
        <div className="detail-actions">
          <Link href="/signin?next=/dealer" className="btn-primary">
            {t("auth_sign_in")}
          </Link>
          <Link href="/pro" className="btn-ghost">
            {t("landing_cta_pro")}
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="dealer-page">
      <div className="explore-command">
        <p className="explore-command-eyebrow">{t("dealer_eyebrow")}</p>
        <h1 className="explore-title">{t("dealer_title")}</h1>
        <p className="explore-lede">{t("dealer_lede")}</p>
      </div>

      {status && !status.allowed ? (
        <div className="dealer-lock">
          <p className="banner-error">{t("dealer_locked")}</p>
          <p className="explore-lede">{t("dealer_locked_lede")}</p>
          <div className="detail-actions">
            {status.checkout_url ? (
              <a href={status.checkout_url} className="btn-primary" rel="noreferrer">
                {t("dealer_upgrade")}
              </a>
            ) : null}
            <Link href="/pro" className="btn-ghost">
              {t("dealer_pro_details")}
            </Link>
          </div>
        </div>
      ) : null}

      {status?.allowed ? (
        <form className="dealer-form" onSubmit={onScore}>
          <div className="filter-row">
            <label>
              <span>{t("dealer_fee")}</span>
              <input
                type="number"
                min={0}
                max={35}
                step={0.5}
                value={fee}
                onChange={(e) => setFee(Number(e.target.value) || 0)}
              />
            </label>
            <label>
              <span>{t("dealer_ship")}</span>
              <input
                type="number"
                min={0}
                max={50}
                step={0.5}
                value={ship}
                onChange={(e) => setShip(Number(e.target.value) || 0)}
              />
            </label>
            <label>
              <span>{t("dealer_csv_file")}</span>
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => onFile(e.target.files?.[0] || null)}
              />
            </label>
          </div>
          <label className="csv-label">
            <span>{t("dealer_csv")}</span>
            <textarea
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              rows={8}
              spellCheck={false}
              title={status.csv_hint || undefined}
            />
          </label>
          <div className="dealer-sync-bar">
            <label className="dealer-autoscore">
              <input
                type="checkbox"
                checked={autoScore}
                onChange={(e) => setAutoScore(e.target.checked)}
              />
              <span>{t("dealer_auto_score")}</span>
            </label>
            {syncedAt ? (
              <span className="dealer-sync-meta">
                {t("dealer_synced", {
                  when: new Date(syncedAt).toLocaleString(),
                })}
              </span>
            ) : (
              <span className="dealer-sync-meta">{t("dealer_not_synced")}</span>
            )}
            {result?.inventory_format === "tcgplayer" ? (
              <span className="dealer-format-pill">{t("dealer_format_tcgplayer")}</span>
            ) : null}
          </div>
          <div className="auth-actions">
            <button
              type="submit"
              className="btn-primary"
              disabled={busy || !csvText.trim()}
            >
              {t("dealer_score")}
            </button>
            {status?.sample_csv ? (
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  setCsvText(status.sample_csv);
                  autoScoredRef.current = false;
                }}
              >
                {t("dealer_sample")}
              </button>
            ) : null}
            {status?.sample_tcgplayer_csv ? (
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  setCsvText(status.sample_tcgplayer_csv || "");
                  autoScoredRef.current = false;
                }}
              >
                {t("dealer_sample_tcgplayer")}
              </button>
            ) : null}
            {syncedAt ? (
              <button type="button" className="btn-ghost" onClick={onClearSync}>
                {t("dealer_clear_sync")}
              </button>
            ) : null}
          </div>
        </form>
      ) : null}

      {error ? <p className="banner-error">{error}</p> : null}

      {status?.allowed && result ? (
        <>
          <div className="kpi-row">
            <div className="kpi-chip">
              <span>{t("dealer_rows")}</span>
              <strong>{result.rows}</strong>
            </div>
            <div className="kpi-chip">
              <span>{t("dealer_matched")}</span>
              <strong>{result.matched}</strong>
            </div>
            <div className="kpi-chip">
              <span>{t("dealer_actions")}</span>
              <strong>{result.actionable}</strong>
            </div>
            <div className="kpi-chip">
              <span>{t("dealer_inv_value")}</span>
              <strong>{formatMoney(result.inventory_value)}</strong>
            </div>
          </div>
          {result.unmatched ? (
            <p className="result-count">
              {t("dealer_unmatched", { n: result.unmatched })}
            </p>
          ) : null}

          <div className="auth-actions dealer-download-actions">
            <button
              type="button"
              className="btn-primary"
              disabled={result.items.length === 0}
              onClick={() =>
                downloadDealerCsv(result.items, "dealer_desk_actions.csv")
              }
            >
              {t("dealer_download")}
            </button>
            <button
              type="button"
              className="btn-ghost"
              disabled={actionable.length === 0}
              onClick={() =>
                downloadDealerCsv(actionable, "dealer_desk_actionable.csv")
              }
            >
              {t("dealer_download_actionable")}
            </button>
          </div>

          <div className="portfolio-section-head">
            <h2>{t("dealer_actionable")}</h2>
          </div>
          {actionable.length === 0 ? (
            <p className="empty-state">{t("dealer_no_actions")}</p>
          ) : (
            <div className="dealer-list">
              {actionable.map((row, idx) => (
                <ActionRow key={`${row.card_id}-${idx}`} row={row} />
              ))}
            </div>
          )}

          <div className="portfolio-section-head">
            <h2>{t("dealer_full")}</h2>
          </div>
          <div className="dealer-list">
            {result.items.map((row, idx) => (
              <ActionRow key={`all-${row.card_id}-${idx}`} row={row} />
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}

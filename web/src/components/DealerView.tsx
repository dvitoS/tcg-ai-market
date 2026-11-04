"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import {
  fetchDealerStatus,
  formatChange,
  formatMoney,
  scoreDealerCsv,
} from "@/lib/api";
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
        <span>net edge {formatChange(row.net_edge_pct)}{band}</span>
      </div>
    </div>
  );
}

export function DealerView() {
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<DealerStatus | null>(null);
  const [csvText, setCsvText] = useState("");
  const [fee, setFee] = useState(13);
  const [ship, setShip] = useState(4);
  const [result, setResult] = useState<DealerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
        setCsvText(st.sample_csv);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Dealer unavailable");
      }
    }
    void boot();
  }, [authLoading, user]);

  async function onScore(event: FormEvent) {
    event.preventDefault();
    if (!user) return;
    setBusy(true);
    setError(null);
    try {
      const scored = await scoreDealerCsv({
        csv_text: csvText,
        fee_pct: fee,
        ship_usd: ship,
      });
      setResult(scored);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Score failed");
    } finally {
      setBusy(false);
    }
  }

  function onFile(file: File | null) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setCsvText(String(reader.result || ""));
    };
    reader.readAsText(file);
  }

  const actionable =
    result?.items.filter((row) => row.action === "LIST" || row.action === "BUY_MORE") || [];

  if (!authLoading && !user) {
    return (
      <section className="dealer-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">Dealer</p>
          <h1 className="explore-title">Desk</h1>
          <p className="explore-lede">
            Sign in to score inventory against the Soft Ink market board.
          </p>
        </div>
        <div className="detail-actions">
          <Link href="/portfolio" className="btn-primary">
            Sign in
          </Link>
          <Link href="/pro" className="btn-ghost">
            Soft Pro
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="dealer-page">
      <div className="explore-command">
        <p className="explore-command-eyebrow">Dealer</p>
        <h1 className="explore-title">Desk</h1>
        <p className="explore-lede">
          Upload inventory CSV, apply sell fee + shipping, and rank LIST / BUY MORE when the
          conformal gate is green.
        </p>
      </div>

      {status && !status.allowed ? (
        <div className="dealer-lock">
          <p className="banner-error">Dealer desk is a Soft Pro surface.</p>
          <p className="explore-lede">
            Upgrade with the same email you use to sign in, then come back to score inventory.
          </p>
          <div className="detail-actions">
            {status.checkout_url ? (
              <a href={status.checkout_url} className="btn-primary" rel="noreferrer">
                Upgrade with Creem
              </a>
            ) : null}
            <Link href="/pro" className="btn-ghost">
              Soft Pro details
            </Link>
          </div>
        </div>
      ) : null}

      {status?.allowed ? (
      <form className="dealer-form" onSubmit={onScore}>
        <div className="filter-row">
          <label>
            <span>Sell fee %</span>
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
            <span>Shipping USD</span>
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
            <span>CSV file</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => onFile(e.target.files?.[0] || null)}
            />
          </label>
        </div>
        <label className="csv-label">
          <span>Inventory CSV</span>
          <textarea
            value={csvText}
            onChange={(e) => setCsvText(e.target.value)}
            rows={8}
            spellCheck={false}
          />
        </label>
        <div className="auth-actions">
          <button type="submit" className="btn-primary" disabled={busy || !csvText.trim()}>
            Score desk
          </button>
          {status?.sample_csv ? (
            <button
              type="button"
              className="btn-ghost"
              onClick={() => setCsvText(status.sample_csv)}
            >
              Load sample
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
              <span>Rows</span>
              <strong>{result.rows}</strong>
            </div>
            <div className="kpi-chip">
              <span>Matched</span>
              <strong>{result.matched}</strong>
            </div>
            <div className="kpi-chip">
              <span>Actions</span>
              <strong>{result.actionable}</strong>
            </div>
            <div className="kpi-chip">
              <span>Inventory value</span>
              <strong>{formatMoney(result.inventory_value)}</strong>
            </div>
          </div>
          {result.unmatched ? (
            <p className="result-count">{result.unmatched} unmatched rows</p>
          ) : null}

          <div className="portfolio-section-head">
            <h2>Actionable</h2>
          </div>
          {actionable.length === 0 ? (
            <p className="empty-state">No LIST / BUY MORE rows under this fee model.</p>
          ) : (
            <div className="dealer-list">
              {actionable.map((row, idx) => (
                <ActionRow key={`${row.card_id}-${idx}`} row={row} />
              ))}
            </div>
          )}

          <div className="portfolio-section-head">
            <h2>Full board</h2>
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

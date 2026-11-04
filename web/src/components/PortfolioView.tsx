"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import {
  deletePortfolioLot,
  fetchPortfolio,
  fetchWatchlist,
  formatChange,
  formatMoney,
  removeWatchlistCard,
} from "@/lib/api";
import type { PortfolioLot, PortfolioSummary, WatchlistItem } from "@/lib/types";

const EMPTY_SUMMARY: PortfolioSummary = {
  lots: 0,
  value: 0,
  invested: 0,
  pnl: 0,
  pnl_pct: 0,
  outlook_value: 0,
  outlook_pct: 0,
};

function pnlClass(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "";
  if (value > 0.01) return "pnl-up";
  if (value < -0.01) return "pnl-down";
  return "";
}

export function PortfolioView() {
  const { user, loading: authLoading, login, logout, ensureDemoSession } = useAuth();
  const [lots, setLots] = useState<PortfolioLot[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary>(EMPTY_SUMMARY);
  const [watch, setWatch] = useState<WatchlistItem[]>([]);
  const [demo, setDemo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("dev@local");
  const [password, setPassword] = useState("demo");

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [portfolio, watchlist] = await Promise.all([
        fetchPortfolio(),
        fetchWatchlist(),
      ]);
      setLots(portfolio.items);
      setSummary(portfolio.summary);
      setDemo(portfolio.demo || watchlist.demo);
      setWatch(watchlist.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load portfolio");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user) return;
    void load();
  }, [authLoading, user, load]);

  async function onLogin(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  async function onRemoveLot(id: number | string) {
    setBusy(true);
    try {
      await deletePortfolioLot(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove lot");
    } finally {
      setBusy(false);
    }
  }

  async function onRemoveWatch(cardId: string) {
    setBusy(true);
    const previous = watch;
    setWatch((prev) => prev.filter((item) => item.card_id !== cardId));
    try {
      await removeWatchlistCard(cardId);
      await load();
    } catch (err) {
      setWatch(previous);
      setError(err instanceof Error ? err.message : "Could not remove watch");
    } finally {
      setBusy(false);
    }
  }

  if (authLoading) {
    return <p className="empty-state">Loading session…</p>;
  }

  if (!user) {
    return (
      <section className="portfolio-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">Portfolio</p>
          <h1 className="explore-title">Sign in</h1>
          <p className="explore-lede">
            Portfolio and watchlist need a session. Local Soft Ink demo accepts any password.
          </p>
        </div>
        <form className="auth-card" onSubmit={onLogin}>
          <label>
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error ? <p className="banner-error">{error}</p> : null}
          <div className="auth-actions">
            <button type="submit" className="btn-primary" disabled={busy}>
              Sign in
            </button>
            <button
              type="button"
              className="btn-ghost"
              disabled={busy}
              onClick={() => {
                void (async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const ok = await ensureDemoSession();
                    if (!ok) {
                      setError("Demo login is disabled in production. Sign in with your account.");
                      return;
                    }
                    await load();
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Demo login failed");
                  } finally {
                    setBusy(false);
                  }
                })();
              }}
            >
              Continue as demo
            </button>
          </div>
        </form>
      </section>
    );
  }

  return (
    <section className="portfolio-page">
      <div className="portfolio-head">
        <div className="explore-command">
          <p className="explore-command-eyebrow">Portfolio</p>
          <h1 className="explore-title">Your book</h1>
          <p className="explore-lede">
            Mark-to-market lots and watchlist alerts — Soft Ink.
            {demo ? " · demo session" : ""}
          </p>
        </div>
        <div className="portfolio-user">
          <span>{user.email || user.id}</span>
          <button type="button" className="btn-ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </div>

      {error ? <p className="banner-error">{error}</p> : null}

      <div className="kpi-row">
        <div className="kpi-chip">
          <span>Value</span>
          <strong>{formatMoney(summary.value)}</strong>
        </div>
        <div className="kpi-chip">
          <span>Invested</span>
          <strong>{formatMoney(summary.invested)}</strong>
        </div>
        <div className={`kpi-chip ${pnlClass(summary.pnl)}`}>
          <span>PnL</span>
          <strong>
            {formatMoney(summary.pnl)} / {formatChange(summary.pnl_pct)}
          </strong>
        </div>
        <div className={`kpi-chip ${pnlClass(summary.outlook_pct)}`}>
          <span>AI outlook</span>
          <strong>
            {formatMoney(summary.outlook_value)} / {formatChange(summary.outlook_pct)}
          </strong>
        </div>
      </div>

      <div className="portfolio-section-head">
        <h2>Open lots · {summary.lots}</h2>
        <button type="button" className="btn-ghost" disabled={busy} onClick={() => void load()}>
          Refresh
        </button>
      </div>

      {lots.length === 0 ? (
        <p className="empty-state">
          No lots yet. Open a card from{" "}
          <Link href="/" className="inline-link">
            Browse
          </Link>{" "}
          and start collecting.
        </p>
      ) : (
        <div className="lot-grid">
          {lots.map((lot) => (
            <article key={String(lot.id)} className="lot-card">
              <Link href={`/cards/${encodeURIComponent(lot.card_id)}`} className="lot-art">
                <Image
                  src={lot.image_url || "/kestrel-logo.png"}
                  alt={lot.name || lot.card_id}
                  width={180}
                  height={252}
                />
              </Link>
              <div className="lot-body">
                <Link href={`/cards/${encodeURIComponent(lot.card_id)}`} className="lot-name">
                  {lot.name || lot.card_id}
                </Link>
                <p className="lot-meta">
                  {lot.quantity}× · {lot.condition || "NM"}
                  {lot.grade ? ` · ${lot.grade}` : ""}
                </p>
                <p className="lot-price">{formatMoney(lot.current_price)}</p>
                <p className={`lot-pnl ${pnlClass(lot.pnl)}`}>
                  {formatMoney(lot.pnl)} · {formatChange(lot.pnl_pct)}
                </p>
                {lot.signal ? (
                  <span className={`explore-card-signal signal-${lot.signal.toLowerCase()}`}>
                    {lot.signal}
                  </span>
                ) : null}
                <button
                  type="button"
                  className="btn-ghost lot-remove"
                  disabled={busy}
                  onClick={() => void onRemoveLot(lot.id)}
                >
                  Remove
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      <div className="portfolio-section-head" id="watchlist">
        <h2>Watchlist · {watch.length}</h2>
      </div>
      {watch.length === 0 ? (
        <p className="empty-state">Watchlist is empty. Star cards from detail pages.</p>
      ) : (
        <div className="watch-list">
          {watch.map((item) => (
            <div key={item.card_id} className="watch-row">
              <Link href={`/cards/${encodeURIComponent(item.card_id)}`} className="watch-art">
                <Image
                  src={item.image_url || "/kestrel-logo.png"}
                  alt={item.name || item.card_id}
                  width={56}
                  height={78}
                />
              </Link>
              <div className="watch-copy">
                <Link href={`/cards/${encodeURIComponent(item.card_id)}`} className="lot-name">
                  {item.name || item.card_id}
                </Link>
                <p className="lot-meta">
                  {[item.set_name, item.rarity].filter(Boolean).join(" · ")}
                </p>
              </div>
              <div className="watch-metrics">
                <strong>{formatMoney(item.market_price)}</strong>
                <span className={pnlClass(item.expected_change_pct)}>
                  {formatChange(item.expected_change_pct)}
                  {item.signal ? ` · ${item.signal}` : ""}
                </span>
              </div>
              <button
                type="button"
                className="btn-ghost"
                disabled={busy}
                onClick={() => void onRemoveWatch(item.card_id)}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

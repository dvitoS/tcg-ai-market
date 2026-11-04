"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useLocale } from "@/components/LocaleProvider";
import { PortfolioBarsChart } from "@/components/PortfolioBarsChart";
import { PortfolioPerfChart } from "@/components/PortfolioPerfChart";
import {
  deletePortfolioLot,
  fetchPortfolio,
  fetchPortfolioPerformance,
  fetchWatchlist,
  fetchWatchlistAlerts,
  forgotPasswordRequest,
  formatChange,
  formatMoney,
  removeWatchlistCard,
  sellPortfolioLot,
  updatePortfolioLot,
} from "@/lib/api";
import { signalLabel } from "@/lib/i18n/messages";
import type {
  PortfolioLot,
  PortfolioPerfPoint,
  PortfolioSummary,
  WatchAlertItem,
  WatchlistItem,
} from "@/lib/types";

import {
  dismissAlert,
  readDismissed,
  readSureOnly,
  readThresholdPct,
  writeSureOnly,
  writeThresholdPct,
} from "@/lib/watchAlertPrefs";

const CONDITIONS = ["NM", "LP", "MP", "HP", "DMG"];

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
  const { locale, t } = useLocale();
  const { user, loading: authLoading, login, signup, logout, ensureDemoSession } = useAuth();
  const [lots, setLots] = useState<PortfolioLot[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary>(EMPTY_SUMMARY);
  const [perfPoints, setPerfPoints] = useState<PortfolioPerfPoint[]>([]);
  const [watch, setWatch] = useState<WatchlistItem[]>([]);
  const [alerts, setAlerts] = useState<WatchAlertItem[]>([]);
  const [sureOnlyAllowed, setSureOnlyAllowed] = useState(true);
  const [demo, setDemo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [authMode, setAuthMode] = useState<"signin" | "signup" | "forgot">("signin");
  const [email, setEmail] = useState("dev@local");
  const [password, setPassword] = useState("demo");
  const [thresholdPct, setThresholdPct] = useState(5);
  const [sureOnly, setSureOnly] = useState(true);
  const [dismissed, setDismissed] = useState<string[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editQty, setEditQty] = useState(1);
  const [editCost, setEditCost] = useState(1);
  const [editCondition, setEditCondition] = useState("NM");
  const [salePrice, setSalePrice] = useState(1);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setThresholdPct(readThresholdPct());
    setSureOnly(readSureOnly());
    setDismissed(readDismissed());
  }, []);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [portfolio, watchlist, digest, performance] = await Promise.all([
        fetchPortfolio({ include_sold: true }),
        fetchWatchlist(),
        fetchWatchlistAlerts({
          threshold_pct: thresholdPct,
          sure_only: sureOnly,
          dismissed,
        }),
        fetchPortfolioPerformance({ max_days: 120 }),
      ]);
      setLots(portfolio.items);
      setSummary(portfolio.summary);
      setPerfPoints(performance.points || []);
      setDemo(portfolio.demo || watchlist.demo || digest.demo || performance.demo);
      setWatch(watchlist.items);
      setAlerts(digest.items);
      setSureOnlyAllowed(digest.sure_only_allowed);
      if (!digest.sure_only_allowed && sureOnly) {
        setSureOnly(false);
        writeSureOnly(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load portfolio");
    } finally {
      setBusy(false);
    }
  }, [dismissed, sureOnly, thresholdPct]);

  const alertCaption = useMemo(() => {
    if (sureOnly) {
      return `Sure-only · conformal BUY/SELL with |AI ROI| ≥ ${thresholdPct.toFixed(0)}%.`;
    }
    return `AI ROI or 7d price move ≥ ${thresholdPct.toFixed(0)}% on cards you watch.`;
  }, [sureOnly, thresholdPct]);

  const openLots = useMemo(
    () => lots.filter((lot) => String(lot.status || "open").toLowerCase() !== "sold"),
    [lots],
  );
  const soldLots = useMemo(
    () => lots.filter((lot) => String(lot.status || "").toLowerCase() === "sold"),
    [lots],
  );

  function beginEdit(lot: PortfolioLot) {
    setEditingId(String(lot.id));
    setEditQty(Math.max(1, Number(lot.quantity) || 1));
    setEditCost(Math.max(0.0001, Number(lot.purchase_price) || 1));
    const cond = String(lot.condition || "NM");
    setEditCondition(CONDITIONS.includes(cond) ? cond : "NM");
    setSalePrice(
      Math.max(
        0.0001,
        Number(lot.current_price ?? lot.market_price ?? lot.purchase_price) || 1,
      ),
    );
    setNotice(null);
  }

  useEffect(() => {
    if (authLoading) return;
    if (!user) return;
    void load();
  }, [authLoading, user, load]);

  async function onLogin(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (authMode === "forgot") {
        const origin =
          typeof window !== "undefined" ? window.location.origin : "";
        const result = await forgotPasswordRequest(
          email.trim(),
          origin ? `${origin}/auth/reset` : undefined,
        );
        setNotice(result.message);
        return;
      }
      if (authMode === "signup") {
        const outcome = await signup(email.trim(), password);
        if (outcome.needsConfirmation) {
          setNotice(
            outcome.message ||
              "Account created. Check your email to confirm, then sign in.",
          );
          setAuthMode("signin");
          return;
        }
        setNotice(outcome.message || "Account created.");
      } else {
        await login(email.trim(), password);
      }
      await load();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : authMode === "signup"
            ? "Sign up failed"
            : authMode === "forgot"
              ? "Could not start password reset"
              : "Login failed",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onRemoveLot(id: number | string) {
    setBusy(true);
    setNotice(null);
    try {
      await deletePortfolioLot(id);
      if (editingId === String(id)) setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove lot");
    } finally {
      setBusy(false);
    }
  }

  async function onSaveLot(event: FormEvent) {
    event.preventDefault();
    if (!editingId) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await updatePortfolioLot(editingId, {
        quantity: editQty,
        purchase_price: editCost,
        condition: editCondition,
      });
      setNotice("Lot updated.");
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update lot");
    } finally {
      setBusy(false);
    }
  }

  async function onSellLot(event: FormEvent) {
    event.preventDefault();
    if (!editingId) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await sellPortfolioLot(editingId, { sale_price: salePrice });
      setNotice("Lot marked sold.");
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sell lot");
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
    return <p className="empty-state">{t("port_loading")}</p>;
  }

  if (!user) {
    return (
      <section className="portfolio-page">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("port_eyebrow")}</p>
          <h1 className="explore-title">
            {authMode === "signup"
              ? t("auth_create_account")
              : authMode === "forgot"
                ? t("auth_forgot_title")
                : t("auth_sign_in")}
          </h1>
          <p className="explore-lede">
            {authMode === "signup"
              ? t("auth_signup_lede")
              : authMode === "forgot"
                ? t("auth_forgot_lede")
                : t("auth_signin_lede")}
          </p>
        </div>
        <form className="auth-card" onSubmit={onLogin}>
          {authMode !== "forgot" ? (
            <div className="auth-mode-toggle" role="tablist" aria-label={t("auth_mode")}>
              <button
                type="button"
                role="tab"
                aria-selected={authMode === "signin"}
                className={authMode === "signin" ? "is-active" : undefined}
                disabled={busy}
                onClick={() => {
                  setAuthMode("signin");
                  setError(null);
                }}
              >
                {t("auth_sign_in")}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={authMode === "signup"}
                className={authMode === "signup" ? "is-active" : undefined}
                disabled={busy}
                onClick={() => {
                  setAuthMode("signup");
                  setError(null);
                  if (email === "dev@local") setEmail("");
                  if (password === "demo") setPassword("");
                }}
              >
                {t("auth_create_account")}
              </button>
            </div>
          ) : null}
          <label>
            <span>{t("auth_email")}</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </label>
          {authMode !== "forgot" ? (
            <label>
              <span>{authMode === "signup" ? t("auth_password_min") : t("auth_password")}</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={authMode === "signup" ? 6 : undefined}
                autoComplete={authMode === "signup" ? "new-password" : "current-password"}
              />
            </label>
          ) : null}
          {error ? <p className="banner-error">{error}</p> : null}
          {notice ? <p className="banner-ok">{notice}</p> : null}
          <div className="auth-actions">
            <button type="submit" className="btn-primary" disabled={busy}>
              {authMode === "signup"
                ? t("auth_create_account")
                : authMode === "forgot"
                  ? t("auth_forgot_submit")
                  : t("auth_sign_in")}
            </button>
            {authMode === "signin" ? (
              <>
                <button
                  type="button"
                  className="btn-ghost"
                  disabled={busy}
                  onClick={() => {
                    setAuthMode("forgot");
                    setError(null);
                    setNotice(null);
                    if (email === "dev@local") setEmail("");
                  }}
                >
                  {t("auth_forgot")}
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
                          setError(t("auth_demo_blocked"));
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
                  {t("auth_demo")}
                </button>
              </>
            ) : null}
            {authMode === "forgot" ? (
              <button
                type="button"
                className="btn-ghost"
                disabled={busy}
                onClick={() => {
                  setAuthMode("signin");
                  setError(null);
                  setNotice(null);
                }}
              >
                {t("auth_forgot_back")}
              </button>
            ) : null}
          </div>
        </form>
      </section>
    );
  }

  return (
    <section className="portfolio-page">
      <div className="portfolio-head">
        <div className="explore-command">
          <p className="explore-command-eyebrow">{t("port_eyebrow")}</p>
          <h1 className="explore-title">{t("port_title")}</h1>
          <p className="explore-lede">
            {t("port_lede")}
            {demo ? ` · ${t("port_demo_session")}` : ""}
          </p>
        </div>
        <div className="portfolio-user">
          <span>{user.email || user.id}</span>
          <button type="button" className="btn-ghost" onClick={logout}>
            {t("auth_sign_out")}
          </button>
        </div>
      </div>

      {error ? <p className="banner-error">{error}</p> : null}
      {notice ? <p className="banner-ok">{notice}</p> : null}

      <div className="alert-digest" aria-live="polite">
        <div className="alert-digest-head">
          <div>
            <h2>{t("alert_digest_title", { n: alerts.length })}</h2>
            <p className="alert-digest-caption">{alertCaption}</p>
          </div>
          <div className="alert-controls">
            <label className="alert-threshold">
              <span>{t("alert_threshold")}</span>
              <input
                type="number"
                min={1}
                max={50}
                step={1}
                value={thresholdPct}
                disabled={busy}
                onChange={(e) => {
                  const next = Number(e.target.value);
                  const clamped = Number.isFinite(next)
                    ? Math.min(50, Math.max(1, next))
                    : 5;
                  setThresholdPct(clamped);
                  writeThresholdPct(clamped);
                }}
              />
            </label>
            <label className="alert-sure">
              <input
                type="checkbox"
                checked={sureOnly && sureOnlyAllowed}
                disabled={busy || !sureOnlyAllowed}
                onChange={(e) => {
                  const next = e.target.checked;
                  setSureOnly(next);
                  writeSureOnly(next);
                }}
              />
              <span>
                {t("alert_sure_only")}
                {sureOnlyAllowed ? "" : t("alert_sure_pro")}
              </span>
            </label>
          </div>
        </div>
        {alerts.length === 0 ? (
          <p className="empty-state alert-digest-empty">
            {sureOnly
              ? t("alert_empty_sure", { n: thresholdPct.toFixed(0) })
              : t("alert_empty", { n: thresholdPct.toFixed(0) })}
          </p>
        ) : (
          <ul className="alert-digest-list">
            {alerts.slice(0, 15).map((alert) => (
              <li key={alert.card_id} className={alert.sure ? "alert-sure-hit" : undefined}>
                <Link href={`/cards/${encodeURIComponent(alert.card_id)}`}>
                  {alert.sure ? "✓ " : ""}
                  {alert.body}
                </Link>
                <button
                  type="button"
                  className="btn-ghost"
                  disabled={busy}
                  onClick={() => {
                    const next = dismissAlert(alert.card_id);
                    setDismissed(next);
                  }}
                >
                  {t("alert_dismiss")}
                </button>
              </li>
            ))}
          </ul>
        )}
        {alerts.length > 15 ? (
          <p className="alert-digest-more">
            {t("alert_more", { n: alerts.length - 15 })}
          </p>
        ) : null}
      </div>

      <div className="kpi-row">
        <div className="kpi-chip">
          <span>{t("kpi_value")}</span>
          <strong>{formatMoney(summary.value)}</strong>
        </div>
        <div className="kpi-chip">
          <span>{t("kpi_invested")}</span>
          <strong>{formatMoney(summary.invested)}</strong>
        </div>
        <div className={`kpi-chip ${pnlClass(summary.pnl)}`}>
          <span>{t("kpi_pnl")}</span>
          <strong>
            {formatMoney(summary.pnl)} / {formatChange(summary.pnl_pct)}
          </strong>
        </div>
        <div className={`kpi-chip ${pnlClass(summary.outlook_pct)}`}>
          <span>{t("kpi_outlook")}</span>
          <strong>
            {formatMoney(summary.outlook_value)} / {formatChange(summary.outlook_pct)}
          </strong>
        </div>
      </div>

      <PortfolioPerfChart points={perfPoints} />
      <PortfolioBarsChart lots={openLots} />

      <div className="portfolio-section-head">
        <h2>{t("port_open_lots", { n: openLots.length })}</h2>
        <button type="button" className="btn-ghost" disabled={busy} onClick={() => void load()}>
          {t("port_refresh")}
        </button>
      </div>

      {openLots.length === 0 ? (
        <p className="empty-state">
          {t("port_no_lots")}{" "}
          <Link href="/browse" className="inline-link">
            {t("nav_browse")}
          </Link>{" "}
          {t("port_and_collect")}
        </p>
      ) : (
        <div className="lot-grid">
          {openLots.map((lot) => (
            <article
              key={String(lot.id)}
              className={`lot-card${editingId === String(lot.id) ? " lot-card-active" : ""}`}
            >
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
                    {signalLabel(locale, lot.signal)}
                  </span>
                ) : null}
                <div className="lot-actions">
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={busy}
                    onClick={() => beginEdit(lot)}
                  >
                    {t("port_edit_sell")}
                  </button>
                  <button
                    type="button"
                    className="btn-ghost lot-remove"
                    disabled={busy}
                    onClick={() => void onRemoveLot(lot.id)}
                  >
                    {t("port_remove")}
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {editingId ? (
        <div className="lot-edit-panel">
          <h2>{t("port_edit_lot", { id: editingId })}</h2>
          <form className="lot-edit-form" onSubmit={onSaveLot}>
            <label>
              <span>{t("port_qty")}</span>
              <input
                type="number"
                min={1}
                step={1}
                value={editQty}
                disabled={busy}
                onChange={(e) => setEditQty(Math.max(1, Number(e.target.value) || 1))}
              />
            </label>
            <label>
              <span>{t("port_purchase")}</span>
              <input
                type="number"
                min={0.0001}
                step={0.01}
                value={editCost}
                disabled={busy}
                onChange={(e) => setEditCost(Math.max(0.0001, Number(e.target.value) || 0.0001))}
              />
            </label>
            <label>
              <span>{t("port_condition")}</span>
              <select
                value={editCondition}
                disabled={busy}
                onChange={(e) => setEditCondition(e.target.value)}
              >
                {CONDITIONS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <div className="lot-edit-actions">
              <button type="submit" className="btn-primary" disabled={busy}>
                {t("port_save_lot")}
              </button>
              <button
                type="button"
                className="btn-ghost"
                disabled={busy}
                onClick={() => setEditingId(null)}
              >
                {t("port_cancel")}
              </button>
            </div>
          </form>
          <form className="lot-sell-form" onSubmit={onSellLot}>
            <label>
              <span>{t("port_sale_price")}</span>
              <input
                type="number"
                min={0.0001}
                step={0.01}
                value={salePrice}
                disabled={busy}
                onChange={(e) => setSalePrice(Math.max(0.0001, Number(e.target.value) || 0.0001))}
              />
            </label>
            <button type="submit" className="btn-primary" disabled={busy}>
              {t("port_mark_sold")}
            </button>
          </form>
        </div>
      ) : null}

      {soldLots.length > 0 ? (
        <>
          <div className="portfolio-section-head">
            <h2>{t("port_sold_lots", { n: soldLots.length })}</h2>
          </div>
          <div className="sold-list">
            {soldLots.map((lot) => (
              <div key={String(lot.id)} className="sold-row">
                <Link href={`/cards/${encodeURIComponent(lot.card_id)}`} className="lot-name">
                  {lot.name || lot.card_id}
                </Link>
                <span>
                  {t("port_sold_meta", {
                    qty: lot.quantity,
                    cost: formatMoney(lot.purchase_price),
                    sale: formatMoney(lot.sale_price),
                  })}
                </span>
                <span className="lot-meta">{lot.sale_date || "—"}</span>
              </div>
            ))}
          </div>
        </>
      ) : null}

      <div className="portfolio-section-head" id="watchlist">
        <h2>{t("port_watchlist", { n: watch.length })}</h2>
      </div>
      {watch.length === 0 ? (
        <p className="empty-state">{t("port_watch_empty")}</p>
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
                  {item.signal ? ` · ${signalLabel(locale, item.signal)}` : ""}
                </span>
              </div>
              <button
                type="button"
                className="btn-ghost"
                disabled={busy}
                onClick={() => void onRemoveWatch(item.card_id)}
              >
                {t("port_remove")}
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

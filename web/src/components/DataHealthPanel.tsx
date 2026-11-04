"use client";

import { useCallback, useEffect, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { fetchDataHealth, resetDataHealth } from "@/lib/api";
import type { DataHealthResponse } from "@/lib/types";

const EMPTY: DataHealthResponse = {
  live: 0,
  db: 0,
  empty: 0,
  fallback: 0,
  error: 0,
  cache_hit: 0,
  attempts: 0,
  miss_or_fallback_pct: 0,
  justtcg_configured: false,
};

export function DataHealthPanel() {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const [stats, setStats] = useState<DataHealthResponse>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setStats(await fetchDataHealth());
    } catch {
      setError(t("obs_load_error"));
    } finally {
      setBusy(false);
    }
  }, [t]);

  useEffect(() => {
    if (!open) return;
    void load();
  }, [open, load]);

  async function onReset() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      setStats(await resetDataHealth());
      setNotice(t("obs_reset_done"));
    } catch {
      setError(t("obs_load_error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={`data-health${open ? " is-open" : ""}`}>
      <button
        type="button"
        className="data-health-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {t("obs_title")}
      </button>
      {open ? (
        <div className="data-health-body">
          <p className="data-health-caption">{t("obs_caption")}</p>
          <p className="data-health-key">
            {stats.justtcg_configured ? t("obs_key_on") : t("obs_key_off")}
          </p>
          <div className="data-health-metrics">
            <div>
              <span>{t("obs_live")}</span>
              <strong>{stats.live}</strong>
            </div>
            <div>
              <span>{t("obs_db")}</span>
              <strong>{stats.db}</strong>
            </div>
            <div>
              <span>{t("obs_fallback")}</span>
              <strong>{stats.fallback}</strong>
            </div>
            <div>
              <span>{t("obs_empty")}</span>
              <strong>{stats.empty}</strong>
            </div>
            <div>
              <span>{t("obs_errors")}</span>
              <strong>{stats.error}</strong>
            </div>
            <div>
              <span>{t("obs_miss_rate")}</span>
              <strong>{Math.round(stats.miss_or_fallback_pct)}%</strong>
            </div>
          </div>
          <p className="data-health-cache">
            {t("obs_cache")}: {stats.cache_hit}
          </p>
          {error ? <p className="data-health-error">{error}</p> : null}
          {notice ? <p className="data-health-notice">{notice}</p> : null}
          <div className="data-health-actions">
            <button type="button" className="btn-ghost" disabled={busy} onClick={() => void load()}>
              {t("obs_refresh")}
            </button>
            <button type="button" className="btn-ghost" disabled={busy} onClick={() => void onReset()}>
              {t("obs_reset")}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

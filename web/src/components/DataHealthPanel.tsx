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
  cards_total: 0,
  cards_with_history: 0,
  history_coverage_pct: 0,
  fresh_history_pct: null,
  sure_rows: 0,
  quotes_total: 0,
  spot_quarantine_rows: 0,
  spot_poison_clusters: 0,
  spot_poison_cluster_sample: [],
  unmatched_sets_count: null,
  unmatched_sets_sample: [],
  spot_qa_captured_at: null,
  board_source: "empty",
};

function fmtPct(value: number | null | undefined, na: string): string {
  if (value == null || Number.isNaN(Number(value))) return na;
  return `${Math.round(Number(value))}%`;
}

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

  const sample = (stats.unmatched_sets_sample || [])
    .slice(0, 6)
    .map((row) => row.set_name || row.set_code)
    .filter(Boolean)
    .join(", ");

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

          <div className="data-health-qa">
            <p className="data-health-qa-title">{t("obs_qa_title")}</p>
            <p className="data-health-caption">{t("obs_qa_caption")}</p>
            <div className="data-health-metrics">
              <div>
                <span>{t("obs_qa_coverage")}</span>
                <strong>
                  {fmtPct(stats.history_coverage_pct, t("obs_qa_na"))}
                </strong>
              </div>
              <div>
                <span>{t("obs_qa_fresh")}</span>
                <strong>
                  {fmtPct(stats.fresh_history_pct ?? null, t("obs_qa_na"))}
                </strong>
              </div>
              <div>
                <span>{t("obs_qa_sure")}</span>
                <strong>
                  {stats.sure_rows ?? 0}
                  {stats.quotes_total
                    ? ` / ${stats.quotes_total}`
                    : ""}
                </strong>
              </div>
              <div>
                <span>{t("obs_qa_unmatched")}</span>
                <strong>
                  {stats.unmatched_sets_count == null
                    ? t("obs_qa_na")
                    : stats.unmatched_sets_count}
                </strong>
              </div>
              <div>
                <span>{t("obs_qa_cards")}</span>
                <strong>
                  {stats.cards_with_history ?? 0} / {stats.cards_total ?? 0}
                </strong>
              </div>
              <div>
                <span>{t("obs_qa_quotes")}</span>
                <strong>{stats.quotes_total ?? 0}</strong>
              </div>
              <div>
                <span>{t("obs_qa_quarantine")}</span>
                <strong>
                  {stats.spot_quarantine_rows ?? 0}
                  {stats.spot_poison_clusters
                    ? ` / ${stats.spot_poison_clusters}`
                    : ""}
                </strong>
              </div>
            </div>
            {sample ? (
              <p className="data-health-cache lot-meta">{sample}</p>
            ) : null}
            {stats.spot_qa_captured_at ? (
              <p className="data-health-cache">
                {t("obs_qa_snapshot", { when: stats.spot_qa_captured_at })}
              </p>
            ) : null}
            <p className="data-health-qa-title">{t("obs_slo_title")}</p>
            <div className="data-health-metrics">
              <div>
                <span>{t("obs_slo_status")}</span>
                <strong>
                  {stats.nightly_slo_ok == null
                    ? t("obs_slo_na")
                    : stats.nightly_slo_ok
                      ? t("obs_slo_ok")
                      : t("obs_slo_fail")}
                </strong>
              </div>
              <div>
                <span>{t("obs_slo_elapsed")}</span>
                <strong>
                  {stats.nightly_elapsed_s == null
                    ? t("obs_slo_na")
                    : `${Math.round(stats.nightly_elapsed_s / 60)}m`}
                </strong>
              </div>
              <div>
                <span>{t("obs_slo_quotes")}</span>
                <strong>
                  {stats.quotes_written == null
                    ? t("obs_slo_na")
                    : stats.quotes_written}
                </strong>
              </div>
            </div>
          </div>

          {error ? <p className="data-health-error">{error}</p> : null}
          {notice ? <p className="data-health-notice">{notice}</p> : null}
          <div className="data-health-actions">
            <button
              type="button"
              className="btn-ghost"
              disabled={busy}
              onClick={() => void load()}
            >
              {t("obs_refresh")}
            </button>
            <button
              type="button"
              className="btn-ghost"
              disabled={busy}
              onClick={() => void onReset()}
            >
              {t("obs_reset")}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import {
  fetchDataHealth,
  fetchFunnelSummary,
  fetchSpotReportSummary,
  fetchSpotSniffPack,
  fetchTrialConversion,
  healOpenSpotReports,
  healPoisonedSpots,
  resetDataHealth,
  type FunnelSummaryResponse,
  type SpotReportSummary,
  type TrialConversionResponse,
} from "@/lib/api";
import type {
  DataHealthResponse,
  SpotHealMode,
  SpotHealResponse,
  SpotSniffPackResponse,
} from "@/lib/types";

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
  const [sniff, setSniff] = useState<SpotSniffPackResponse | null>(null);
  const [sniffBusy, setSniffBusy] = useState(false);
  const [healBusy, setHealBusy] = useState(false);
  const [healResult, setHealResult] = useState<SpotHealResponse | null>(null);
  const [funnel, setFunnel] = useState<FunnelSummaryResponse | null>(null);
  const [trial, setTrial] = useState<TrialConversionResponse | null>(null);
  const [reports, setReports] = useState<SpotReportSummary | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [health, funnelSummary, trialSummary, reportSummary] =
        await Promise.all([
          fetchDataHealth(),
          fetchFunnelSummary().catch(() => null),
          fetchTrialConversion().catch(() => null),
          fetchSpotReportSummary().catch(() => null),
        ]);
      setStats(health);
      setFunnel(funnelSummary);
      setTrial(trialSummary);
      setReports(reportSummary);
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

  async function onLoadSniff() {
    setSniffBusy(true);
    setError(null);
    try {
      setSniff(await fetchSpotSniffPack(20));
    } catch {
      setError(t("obs_load_error"));
    } finally {
      setSniffBusy(false);
    }
  }

  async function applyHealResult(result: SpotHealResponse) {
    setHealResult(result);
    setNotice(
      t("obs_heal_done", {
        mode: result.mode,
        count: result.count,
        updated: result.updated,
        nulled: result.nulled,
        quotes: result.quotes_quarantined ?? 0,
      }),
    );
    setStats(await fetchDataHealth());
    setReports(await fetchSpotReportSummary().catch(() => null));
  }

  async function onHeal(mode: SpotHealMode) {
    if (mode !== "dry_run") {
      const ok = window.confirm(t("obs_heal_confirm", { mode }));
      if (!ok) return;
    }
    setHealBusy(true);
    setError(null);
    setNotice(null);
    try {
      await applyHealResult(await healPoisonedSpots({ mode, limit: 50 }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("obs_load_error"));
    } finally {
      setHealBusy(false);
    }
  }

  async function onHealOpenReports() {
    const ok = window.confirm(t("obs_heal_confirm", { mode: "refetch" }));
    if (!ok) return;
    setHealBusy(true);
    setError(null);
    setNotice(null);
    try {
      await applyHealResult(
        await healOpenSpotReports({ mode: "refetch", limit: 30 }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : t("obs_load_error"));
    } finally {
      setHealBusy(false);
    }
  }

  async function onHealSniffCard(cardId: string, name: string) {
    const ok = window.confirm(t("obs_sniff_heal_confirm", { name }));
    if (!ok) return;
    setHealBusy(true);
    setError(null);
    setNotice(null);
    try {
      await applyHealResult(
        await healPoisonedSpots({
          mode: "refetch",
          limit: 1,
          cardIds: [cardId],
        }),
      );
      setSniff(await fetchSpotSniffPack(20));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("obs_load_error"));
    } finally {
      setHealBusy(false);
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

            <p className="data-health-qa-title">{t("obs_heal_title")}</p>
            <p className="data-health-caption">{t("obs_heal_caption")}</p>
            {(stats.spot_poison_cluster_sample || []).length > 0 ? (
              <ul className="data-health-sniff-list">
                {(stats.spot_poison_cluster_sample || []).slice(0, 6).map((row) => (
                  <li key={`poison-${row.price}-${row.count}`}>
                    <strong>
                      {t("obs_heal_cluster", {
                        price:
                          row.price != null
                            ? `$${Number(row.price).toFixed(2)}`
                            : "—",
                        count: row.count ?? 0,
                        sets: row.sets ?? 0,
                      })}
                    </strong>
                    {row.rarities?.length ? (
                      <span className="lot-meta">{row.rarities.join(" · ")}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="data-health-caption">{t("obs_heal_clean")}</p>
            )}
            <div className="data-health-actions">
              <button
                type="button"
                className="btn-ghost"
                disabled={healBusy || busy}
                onClick={() => void onHeal("dry_run")}
              >
                {t("obs_heal_dry")}
              </button>
              <button
                type="button"
                className="btn-ghost"
                disabled={healBusy || busy}
                onClick={() => void onHeal("null_market")}
              >
                {t("obs_heal_null")}
              </button>
              <button
                type="button"
                className="btn-ghost"
                disabled={healBusy || busy}
                onClick={() => void onHeal("clear_history")}
              >
                {t("obs_heal_clear")}
              </button>
              <button
                type="button"
                className="btn-ghost"
                disabled={healBusy || busy}
                onClick={() => void onHeal("refetch")}
              >
                {t("obs_heal_refetch")}
              </button>
            </div>
            {healResult ? (
              <p className="data-health-cache">
                {t("obs_heal_summary", {
                  count: healResult.count,
                  keys: healResult.poison_keys.slice(0, 4).join(", ") || "—",
                  skip_poison: healResult.skip_poison,
                  skip_absurd: healResult.skip_absurd,
                })}
              </p>
            ) : null}
          </div>

          <div className="data-health-qa">
            <p className="data-health-qa-title">{t("obs_reports_title")}</p>
            <p className="data-health-caption">{t("obs_reports_caption")}</p>
            {reports ? (
              <>
                <div className="data-health-metrics">
                  <div>
                    <span>{t("obs_reports_open")}</span>
                    <strong>{reports.open_total}</strong>
                  </div>
                  <div>
                    <span>{t("obs_reports_overdue")}</span>
                    <strong>{reports.overdue_heal}</strong>
                  </div>
                </div>
                <p className="data-health-cache lot-meta">
                  {t("obs_reports_meta", {
                    age:
                      reports.oldest_open_age_h == null
                        ? "—"
                        : reports.oldest_open_age_h.toFixed(1),
                    ack: reports.ack_sla_hours,
                    heal: reports.heal_sla_hours,
                  })}
                </p>
                {reports.recent.slice(0, 6).map((row) => (
                  <p key={row.id} className="data-health-cache lot-meta">
                    {row.status} · {row.card_id}
                    {row.spot != null ? ` · $${Number(row.spot).toFixed(2)}` : ""}
                  </p>
                ))}
                <div className="data-health-actions">
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={
                      healBusy || busy || (reports.open_total ?? 0) < 1
                    }
                    onClick={() => void onHealOpenReports()}
                  >
                    {t("obs_reports_heal_open")}
                  </button>
                </div>
              </>
            ) : (
              <p className="data-health-caption">{t("obs_reports_empty")}</p>
            )}
          </div>

          <div className="data-health-qa">
            <p className="data-health-qa-title">{t("obs_trial_title")}</p>
            <p className="data-health-caption">{t("obs_trial_caption")}</p>
            {trial ? (
              <>
                <div className="data-health-metrics">
                  <div>
                    <span>{t("obs_trial_trialing")}</span>
                    <strong>{trial.trialing}</strong>
                  </div>
                  <div>
                    <span>{t("obs_trial_active")}</span>
                    <strong>{trial.active}</strong>
                  </div>
                  <div>
                    <span>{t("obs_trial_canceled")}</span>
                    <strong>{trial.canceled}</strong>
                  </div>
                  <div>
                    <span>{t("obs_trial_paid_share")}</span>
                    <strong>
                      {trial.paid_share_pct == null
                        ? t("obs_na")
                        : `${Math.round(trial.paid_share_pct)}%`}
                    </strong>
                  </div>
                </div>
                <p className="data-health-cache lot-meta">
                  {t("obs_trial_meta", {
                    entitled: trial.entitled,
                    source: trial.source,
                    webhooks: trial.webhook_outcomes.counts?.total ?? 0,
                  })}
                </p>
              </>
            ) : (
              <p className="data-health-caption">{t("obs_trial_empty")}</p>
            )}
          </div>

          <div className="data-health-qa">
            <p className="data-health-qa-title">{t("obs_funnel_title")}</p>
            <p className="data-health-caption">{t("obs_funnel_caption")}</p>
            {funnel ? (
              <>
                <p className="data-health-cache">
                  {t("obs_funnel_total", { n: funnel.total })}
                </p>
                <div className="data-health-metrics">
                  {                    (
                    [
                      "landing_view",
                      "dotd_cta",
                      "pro_view",
                      "pro_checkout_click",
                      "radar_activate",
                      "trade_activate",
                      "share_copy",
                      "share_png",
                    ] as const
                  ).map((key) => (
                    <div key={key}>
                      <span>{key}</span>
                      <strong>{funnel.counts[key] ?? 0}</strong>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="data-health-caption">{t("obs_funnel_empty")}</p>
            )}
          </div>

          <div className="data-health-qa">
            <p className="data-health-qa-title">{t("obs_sniff_title")}</p>
            <p className="data-health-caption">{t("obs_sniff_caption")}</p>
            <div className="data-health-actions">
              <button
                type="button"
                className="btn-ghost"
                disabled={sniffBusy || busy}
                onClick={() => void onLoadSniff()}
              >
                {t("obs_sniff_load")}
              </button>
            </div>
            {sniff ? (
              sniff.count === 0 ? (
                <p className="data-health-caption">{t("obs_sniff_empty")}</p>
              ) : (
                <>
                  <p className="data-health-cache">
                    {t("obs_sniff_meta", {
                      under: sniff.under_n,
                      over: sniff.over_n,
                      source: sniff.board_source,
                    })}
                  </p>
                  <p className="data-health-caption">{sniff.instructions}</p>
                  <ul className="data-health-sniff-list">
                    {sniff.items.map((item) => (
                      <li key={`${item.side}-${item.card_id}`}>
                        <span
                          className={
                            item.side === "UNDER" ? "is-buy" : "is-sell"
                          }
                        >
                          {item.side === "UNDER"
                            ? t("obs_sniff_under")
                            : t("obs_sniff_over")}
                        </span>
                        <strong>{item.name}</strong>
                        <span className="lot-meta">
                          {[item.set_name, item.spot != null ? `$${Number(item.spot).toFixed(2)}` : null]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                        <span className="data-health-sniff-links">
                          {item.tcgplayer_url ? (
                            <a
                              href={item.tcgplayer_url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {t("obs_sniff_open_tcp")}
                            </a>
                          ) : null}
                          <a href={item.kestrel_path}>
                            {t("obs_sniff_open_kestrel")}
                          </a>
                          <button
                            type="button"
                            className="btn-ghost"
                            disabled={healBusy || busy}
                            onClick={() =>
                              void onHealSniffCard(item.card_id, item.name)
                            }
                          >
                            {t("obs_sniff_heal")}
                          </button>
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              )
            ) : null}
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

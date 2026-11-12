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
  sweepDeskPoison,
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

  function showHealNotice(result: SpotHealResponse) {
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
  }

  function refreshHealStats() {
    void fetchDataHealth()
      .then(setStats)
      .catch(() => {});
    void fetchSpotReportSummary()
      .then(setReports)
      .catch(() => {});
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
      showHealNotice(await healPoisonedSpots({ mode, limit: 50 }));
      refreshHealStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("obs_load_error"));
    } finally {
      setHealBusy(false);
    }
  }

  async function onHealAutoUnsafe() {
    const ok = window.confirm(t("obs_heal_auto_confirm"));
    if (!ok) return;
    setHealBusy(true);
    setError(null);
    setNotice(null);
    try {
      // Full drain (auto-unsafe + poison clusters) — same path nightly runs
      // after retrain so ops never needs 10-at-a-time Heal clicks.
      showHealNotice(await sweepDeskPoison());
      refreshHealStats();
      reloadSniffInBackground();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("obs_load_error"));
    } finally {
      setHealBusy(false);
    }
  }

  async function onHealOpenReports() {
    const ok = window.confirm(t("obs_heal_confirm", { mode: "null_market" }));
    if (!ok) return;
    setHealBusy(true);
    setError(null);
    setNotice(null);
    try {
      // Fast path: quarantine board quotes without waiting on JustTCG.
      showHealNotice(
        await healOpenSpotReports({ mode: "null_market", limit: 30 }),
      );
      refreshHealStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("obs_load_error"));
    } finally {
      setHealBusy(false);
    }
  }

  function dropHealedFromSniff(cardIds: string[]) {
    if (!sniff) return;
    const drop = new Set(cardIds);
    const items = sniff.items.filter((item) => !drop.has(String(item.card_id)));
    setSniff({
      ...sniff,
      items,
      count: items.length,
      under_n: items.filter((item) => item.side === "UNDER").length,
      over_n: items.filter((item) => item.side === "OVER").length,
    });
  }

  function reloadSniffInBackground() {
    void fetchSpotSniffPack(20)
      .then(setSniff)
      .catch(() => {});
    refreshHealStats();
  }

  async function onHealSniffCard(cardId: string, name: string) {
    const ok = window.confirm(t("obs_sniff_heal_confirm", { name }));
    if (!ok) return;
    setHealBusy(true);
    setError(null);
    setNotice(null);
    try {
      // null_market is fast (no JustTCG); quarantine drops the row from sure desk.
      const result = await healPoisonedSpots({
        mode: "null_market",
        limit: 1,
        cardIds: [cardId],
      });
      showHealNotice(result);
      if ((result.quotes_quarantined ?? 0) < 1) {
        setError(t("obs_sniff_heal_no_quote"));
      } else {
        dropHealedFromSniff([cardId]);
      }
      // Don't block the next Heal click on a full board sniff reload.
      reloadSniffInBackground();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("obs_load_error"));
    } finally {
      setHealBusy(false);
    }
  }

  async function onHealSniffAll(side?: "UNDER" | "OVER") {
    if (!sniff?.items.length) return;
    const targets = sniff.items.filter((item) =>
      side ? item.side === side : true,
    );
    const cardIds = [
      ...new Set(
        targets
          .map((item) => String(item.card_id || "").trim())
          .filter(Boolean),
      ),
    ];
    if (!cardIds.length) return;
    const ok = window.confirm(
      t("obs_sniff_heal_all_confirm", {
        n: cardIds.length,
        side: side
          ? side === "UNDER"
            ? t("obs_sniff_under")
            : t("obs_sniff_over")
          : t("obs_sniff_all_sides"),
      }),
    );
    if (!ok) return;
    setHealBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await healPoisonedSpots({
        mode: "null_market",
        limit: cardIds.length,
        cardIds,
      });
      showHealNotice(result);
      if ((result.quotes_quarantined ?? 0) < 1) {
        setError(t("obs_sniff_heal_no_quote"));
      } else {
        dropHealedFromSniff(cardIds);
      }
      reloadSniffInBackground();
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
                onClick={() => void onHealAutoUnsafe()}
              >
                {t("obs_heal_auto")}
              </button>
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
                {trial.g3_trust ? (
                  <div className="data-health-qa nested">
                    <p className="data-health-qa-title">{t("obs_g3_title")}</p>
                    <p className="data-health-caption">{t("obs_g3_caption")}</p>
                    <div className="data-health-metrics">
                      <div>
                        <span>{t("obs_g3_wrong_pct")}</span>
                        <strong>
                          {trial.g3_trust.wrong_price_pct == null
                            ? t("obs_na")
                            : `${trial.g3_trust.wrong_price_pct}%`}
                        </strong>
                      </div>
                      <div>
                        <span>{t("obs_g3_cancels")}</span>
                        <strong>{trial.g3_trust.cancel_events}</strong>
                      </div>
                      <div>
                        <span>{t("obs_g3_refunds")}</span>
                        <strong>{trial.g3_trust.refund_events}</strong>
                      </div>
                      <div>
                        <span>{t("obs_g3_reports")}</span>
                        <strong>
                          {trial.g3_trust.spot_reports_per_100_entitled == null
                            ? t("obs_na")
                            : trial.g3_trust.spot_reports_per_100_entitled}
                        </strong>
                      </div>
                    </div>
                    <p className="data-health-cache lot-meta">
                      {trial.g3_trust.gate_ok
                        ? t("obs_g3_ok")
                        : t("obs_g3_fail")}
                      {trial.g3_trust.cited_total === 0
                        ? ` · ${t("obs_g3_empty")}`
                        : ""}
                    </p>
                  </div>
                ) : null}
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
                  {t("obs_funnel_total", {
                    n: funnel.total,
                    source: funnel.source || "memory",
                  })}
                </p>
                <div className="data-health-metrics">
                  {(
                    [
                      "landing_view",
                      "landing_cta_dotd",
                      "landing_cta_pro",
                      "dotd_view",
                      "dotd_card_open",
                      "dotd_cta",
                      "pro_view",
                      "pro_checkout_click",
                      "radar_activate",
                      "trade_activate",
                      "share_copy",
                      "share_png",
                      "spot_report",
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
              <button
                type="button"
                className="btn-ghost"
                disabled={
                  healBusy ||
                  busy ||
                  !sniff?.items.some((item) => item.side === "UNDER")
                }
                onClick={() => void onHealSniffAll("UNDER")}
              >
                {t("obs_sniff_heal_under")}
              </button>
              <button
                type="button"
                className="btn-ghost"
                disabled={healBusy || busy || !sniff?.items.length}
                onClick={() => void onHealSniffAll()}
              >
                {t("obs_sniff_heal_all")}
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
                  <p className="data-health-cache">
                    {t("obs_sniff_verdict_meta", {
                      pass: sniff.verdict_pass ?? 0,
                      review: sniff.verdict_review ?? 0,
                      fail: sniff.verdict_fail ?? 0,
                      healed: sniff.healed_n ?? 0,
                    })}
                  </p>
                  <p className="data-health-cache">
                    {t("obs_sniff_diag_meta", {
                      missing: sniff.tcp_missing ?? 0,
                      resolved: sniff.tcp_resolved ?? 0,
                      rejected: sniff.tcp_rejected ?? 0,
                      jt: sniff.live_configured
                        ? t("obs_sniff_diag_on")
                        : t("obs_sniff_diag_off"),
                      ebay: sniff.ebay_usable
                        ? t("obs_sniff_diag_on")
                        : t("obs_sniff_diag_off"),
                    })}
                  </p>
                  {sniff.live_error ? (
                    <p className="data-health-error">{sniff.live_error}</p>
                  ) : null}
                  {sniff.ebay_error ? (
                    <p className="data-health-error">{sniff.ebay_error}</p>
                  ) : null}
                  <p
                    className={
                      sniff.g0_ready
                        ? "data-health-notice"
                        : "data-health-caption"
                    }
                  >
                    {sniff.g0_ready
                      ? t("obs_sniff_g0_ready")
                      : t("obs_sniff_g0_not_ready")}
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
                        <span
                          className={`data-health-sniff-status is-${item.verdict || "review"}`}
                        >
                          {t(
                            item.verdict === "pass"
                              ? "obs_sniff_verdict_pass"
                              : item.verdict === "fail"
                                ? "obs_sniff_verdict_fail"
                                : "obs_sniff_verdict_review",
                          )}
                        </span>
                        <strong>{item.name}</strong>
                        <span className="lot-meta">
                          {item.tcp_live != null && item.spot != null
                            ? t("obs_sniff_vs_tcp", {
                                spot: `$${Number(item.spot).toFixed(2)}`,
                                tcp: `$${Number(item.tcp_live).toFixed(2)}`,
                                delta:
                                  item.tcp_delta_pct != null
                                    ? `${item.tcp_delta_pct > 0 ? "+" : ""}${Number(item.tcp_delta_pct).toFixed(1)}%`
                                    : "—",
                              })
                            : [
                                item.set_name,
                                item.spot != null
                                  ? `$${Number(item.spot).toFixed(2)}`
                                  : null,
                              ]
                                .filter(Boolean)
                                .join(" · ")}
                          {item.ebay_median != null
                            ? ` · ${t("obs_sniff_vs_ebay", {
                                ebay: `$${Number(item.ebay_median).toFixed(2)}`,
                                n: item.ebay_n ?? 0,
                                delta:
                                  item.ebay_delta_pct != null
                                    ? `${item.ebay_delta_pct > 0 ? "+" : ""}${Number(item.ebay_delta_pct).toFixed(1)}%`
                                    : "—",
                              })}`
                            : ""}
                          {item.skip_reason === "no_tcp_id" ||
                          item.skip_reason === "justtcg_key_missing"
                            ? ` · ${t("obs_sniff_skip_no_tcp")}`
                            : ""}
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

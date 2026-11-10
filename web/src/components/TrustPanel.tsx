"use client";

import { useCallback, useEffect, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { fetchTrustReport, formatChange, getAccessToken } from "@/lib/api";
import type { MessageKey } from "@/lib/i18n/messages";
import type { TrustResponse } from "@/lib/types";

function fmt(value?: number | null, digits = 2): string {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  return Number(value).toFixed(digits);
}

function trustErrorMessage(
  err: unknown,
  t: (key: MessageKey) => string,
): string {
  const code = err instanceof Error ? err.message : "";
  if (code === "TRUST_NOT_FOUND") return t("trust_error_not_found");
  if (code === "TRUST_AUTH") return t("trust_error_auth");
  if (code === "TRUST_PRO") return t("trust_error_pro");
  if (code.startsWith("{") && code.includes("detail")) return t("trust_error");
  return code || t("trust_error");
}

export function TrustPanel({ minEdge = 0 }: { minEdge?: number }) {
  const { t } = useLocale();
  const [data, setData] = useState<TrustResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const edgeFloor = Number.isFinite(minEdge) ? Math.max(0, Number(minEdge)) : 0;

  const load = useCallback(() => {
    setReloadKey((n) => n + 1);
  }, []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    if (!getAccessToken()) {
      setData(null);
      setError(t("trust_error_auth"));
      setLoading(false);
      return () => {
        alive = false;
      };
    }
    void fetchTrustReport({
      horizon_days: 7,
      sample_n: 60,
      min_edge: edgeFloor,
    })
      .then((payload) => {
        if (!alive) return;
        setData(payload);
        setError(null);
      })
      .catch((err) => {
        if (!alive) return;
        setData(null);
        setError(trustErrorMessage(err, t));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [t, reloadKey, edgeFloor]);

  const cal = data?.calibration;
  const cov = data?.conformal_coverage;
  const bt = data?.radar_backtest;

  return (
    <section className="trust-panel" aria-label={t("trust_title")}>
      <div className="chart-head">
        <div>
          <p className="explore-command-eyebrow">{t("trust_eyebrow")}</p>
          <h2>{t("trust_title")}</h2>
          <p>{t("trust_lede")}</p>
        </div>
        {data?.trained_at ? (
          <p className="lot-meta">
            {t("trust_trained", { when: String(data.trained_at).slice(0, 10) })}
            {data.source === "demo" ? ` · ${t("explore_demo")}` : ""}
          </p>
        ) : null}
      </div>

      {loading ? <p className="explore-lede">{t("trust_loading")}</p> : null}
      {error ? (
        <div className="trust-error-row">
          <p className="form-error">{error}</p>
          <button type="button" className="btn-ghost" onClick={load}>
            {t("trust_retry")}
          </button>
        </div>
      ) : null}

      {data ? (
        <>
          <div className="stat-row trust-kpis">
            <div className="stat-chip">
              <span>{t("trust_kpi_direction")}</span>
              <strong>
                {cal?.direction_accuracy_pct != null
                  ? formatChange(cal.direction_accuracy_pct, 1)
                  : "—"}
              </strong>
            </div>
            <div className="stat-chip">
              <span>{t("trust_kpi_rmse_naive")}</span>
              <strong>
                {cal?.rmse_vs_naive != null ? `${fmt(cal.rmse_vs_naive, 2)}×` : "—"}
              </strong>
            </div>
            <div className="stat-chip">
              <span>{t("trust_kpi_coverage")}</span>
              <strong>
                {cov?.coverage_pct != null
                  ? `${fmt(cov.coverage_pct, 1)}%`
                  : "—"}
              </strong>
            </div>
            <div className="stat-chip">
              <span>{t("trust_kpi_radar_hit")}</span>
              <strong>
                {bt?.hit_rate_pct != null ? `${fmt(bt.hit_rate_pct, 1)}%` : "—"}
              </strong>
            </div>
          </div>

          <div className="trust-grid">
            <div className="trust-block">
              <h3>{t("trust_cal_title")}</h3>
              <ul className="trust-list">
                <li>
                  <span>RMSE</span>
                  <strong>{fmt(cal?.rmse, 3)}</strong>
                </li>
                <li>
                  <span>R²</span>
                  <strong>{fmt(cal?.r2, 3)}</strong>
                </li>
                <li>
                  <span>{t("trust_cal_conformal_q")}</span>
                  <strong>
                    {cal?.conformal_q != null
                      ? formatChange(cal.conformal_q, 1)
                      : "—"}
                  </strong>
                </li>
                <li>
                  <span>{t("trust_cal_wf")}</span>
                  <strong>
                    {cal?.wf_direction_accuracy_pct != null
                      ? formatChange(cal.wf_direction_accuracy_pct, 1)
                      : "—"}
                    {cal?.wf_folds != null ? ` · ${cal.wf_folds} folds` : ""}
                  </strong>
                </li>
              </ul>
            </div>

            <div className="trust-block">
              <h3>{t("trust_cov_title")}</h3>
              <p className="lot-meta">
                {cov?.coverage_pct != null
                  ? `${fmt(cov.coverage_pct, 1)}%`
                  : "—"}
                {" · "}
                {t("trust_cov_target", { pct: fmt(cov?.target_pct, 0) })}
                {cov?.n ? ` · n=${cov.n}` : ""}
              </p>
              <p className="explore-lede">{cov?.note || t("trust_cov_empty")}</p>
            </div>

            <div className="trust-block">
              <h3>{t("trust_bt_title")}</h3>
              <p className="lot-meta">
                {t("trust_bt_meta", {
                  days: bt?.horizon_days ?? data.horizon_days,
                  under: bt?.under_n ?? 0,
                  over: bt?.over_n ?? 0,
                })}
                {edgeFloor > 0
                  ? ` · ${t("trust_bt_min_edge", { edge: edgeFloor })}`
                  : ""}
              </p>
              <p className="explore-lede">
                {bt?.n
                  ? t("trust_bt_lede", {
                      hit: fmt(bt.hit_rate_pct, 1),
                      move: fmt(bt.avg_move_pct, 1),
                    })
                  : t("trust_bt_empty")}
              </p>
              {bt?.tighten_suggested ? (
                <p className="form-error">{t("trust_bt_tighten")}</p>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}

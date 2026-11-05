"use client";

import { useEffect, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { fetchTrustReport, formatChange } from "@/lib/api";
import type { TrustResponse } from "@/lib/types";

function fmt(value?: number | null, digits = 2): string {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  return Number(value).toFixed(digits);
}

export function TrustPanel() {
  const { t } = useLocale();
  const [data, setData] = useState<TrustResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    void fetchTrustReport({ horizon_days: 7, sample_n: 60 })
      .then((payload) => {
        if (!alive) return;
        setData(payload);
        setError(null);
      })
      .catch((err) => {
        if (!alive) return;
        setData(null);
        setError(err instanceof Error ? err.message : t("trust_error"));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [t]);

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
      {error ? <p className="form-error">{error}</p> : null}

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
              </p>
              <p className="explore-lede">
                {bt?.n
                  ? t("trust_bt_lede", {
                      hit: fmt(bt.hit_rate_pct, 1),
                      move: fmt(bt.avg_move_pct, 1),
                    })
                  : t("trust_bt_empty")}
              </p>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}

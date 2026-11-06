"use client";

import { useEffect, useMemo, useState } from "react";

import { GradingSensitivityChart } from "@/components/GradingSensitivityChart";
import { useLocale } from "@/components/LocaleProvider";
import { fetchCardPriceSources, formatChange, formatMoney } from "@/lib/api";
import {
  DEFAULT_GRADE_FEE_USD,
  DEFAULT_SELL_FEE_PCT,
  DEFAULT_SHIP_USD,
  GRADE_FEE_PRESETS,
  type GradeFeePresetId,
  computeGradingEv,
  gradingSensitivity,
  matchFeePreset,
} from "@/lib/gradingEv";
import type { MessageKey } from "@/lib/i18n/messages";
import {
  RAW_CONDITIONS,
  adjustNmPrice,
  normalizeCondition,
} from "@/lib/lotPriceAdjust";

function lastPrice(
  points: Array<{ price: number }> | undefined,
): number | null {
  if (!points?.length) return null;
  const n = Number(points[points.length - 1]?.price);
  return Number.isFinite(n) ? n : null;
}

function presetLabelKey(id: GradeFeePresetId): MessageKey {
  if (id === "psa_value") return "grade_ev_preset_psa_value";
  if (id === "psa_regular") return "grade_ev_preset_psa_regular";
  if (id === "psa_express") return "grade_ev_preset_psa_express";
  if (id === "cgc_standard") return "grade_ev_preset_cgc";
  return "grade_ev_preset_custom";
}

export function GradingEvPanel({
  cardId,
  rawPrice,
}: {
  cardId: string;
  rawPrice?: number | null;
}) {
  const { t } = useLocale();
  const [psa10, setPsa10] = useState<number | null>(null);
  const [psa9, setPsa9] = useState<number | null>(null);
  const [sales10, setSales10] = useState<number | null>(null);
  const [sales9, setSales9] = useState<number | null>(null);
  const [periodKey, setPeriodKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [fee, setFee] = useState(DEFAULT_GRADE_FEE_USD);
  const [ship, setShip] = useState(DEFAULT_SHIP_USD);
  const [sellFee, setSellFee] = useState(DEFAULT_SELL_FEE_PCT);
  const [condition, setCondition] = useState("NM");
  const [preset, setPreset] = useState<GradeFeePresetId>("psa_regular");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    // PSA 10 only — PSA 9 uses the built-in ratio in computeGradingEv (saves quota).
    void fetchCardPriceSources(cardId, { grades: "psa10" })
      .then((payload) => {
        if (!alive) return;
        if (payload.psa10_error) {
          setError(payload.psa10_error);
        }
        // Prefer series spot; fall back to markets[].price / last_price from stats.
        const fromSeries = lastPrice(payload.psa10);
        const fromStats = Number(payload.psa10_stats?.price);
        setPsa10(
          fromSeries ??
            (Number.isFinite(fromStats) && fromStats > 0 ? fromStats : null),
        );
        setPsa9(null);
        const s10 = payload.psa10_stats?.sales_count;
        setSales10(s10 != null && Number.isFinite(Number(s10)) ? Number(s10) : null);
        setSales9(null);
        setPeriodKey(payload.psa10_stats?.period_key || null);
      })
      .catch((err) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : t("grade_ev_error"));
        setPsa10(null);
        setPsa9(null);
        setSales10(null);
        setSales9(null);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [cardId, t]);

  const adjustedRaw = useMemo(
    () => adjustNmPrice(rawPrice, { condition: normalizeCondition(condition) }),
    [rawPrice, condition],
  );

  const ev = useMemo(
    () =>
      computeGradingEv({
        rawUsd: adjustedRaw,
        psa10Usd: psa10,
        psa9Usd: psa9,
        gradeFeeUsd: fee,
        shipUsd: ship,
        sellFeePct: sellFee,
      }),
    [adjustedRaw, psa10, psa9, fee, ship, sellFee],
  );

  const curve = useMemo(
    () =>
      gradingSensitivity({
        rawUsd: adjustedRaw,
        gradeFeeUsd: fee,
        shipUsd: ship,
        sellFeePct: sellFee,
        centerPsa10Usd: psa10 ?? ev.breakeven_psa10_usd,
        steps: 25,
        span: 0.45,
      }),
    [adjustedRaw, fee, ship, sellFee, psa10, ev.breakeven_psa10_usd],
  );

  const netClass =
    ev.psa10.net_usd == null
      ? ""
      : ev.psa10.net_usd > 0
        ? "pnl-up"
        : ev.psa10.net_usd < 0
          ? "pnl-down"
          : "";

  const onPreset = (id: GradeFeePresetId) => {
    setPreset(id);
    if (id === "custom") return;
    const hit = GRADE_FEE_PRESETS.find((p) => p.id === id);
    if (!hit) return;
    setFee(hit.gradeFeeUsd);
    setShip(hit.shipUsd);
  };

  const onFeeChange = (next: number) => {
    setFee(next);
    setPreset(matchFeePreset(next, ship));
  };

  const onShipChange = (next: number) => {
    setShip(next);
    setPreset(matchFeePreset(fee, next));
  };

  return (
    <section className="grade-ev-panel" aria-label={t("grade_ev_title")}>
      <div className="detail-ai-head">
        <h2>{t("grade_ev_title")}</h2>
      </div>
      <p className="grade-ev-lede">{t("grade_ev_lede")}</p>

      <div className="grade-ev-inputs">
        <label>
          <span>{t("grade_ev_preset")}</span>
          <select
            value={preset}
            onChange={(e) => onPreset(e.target.value as GradeFeePresetId)}
          >
            {GRADE_FEE_PRESETS.map((p) => (
              <option key={p.id} value={p.id}>
                {t(presetLabelKey(p.id))}
              </option>
            ))}
            <option value="custom">{t("grade_ev_preset_custom")}</option>
          </select>
        </label>
        <label>
          <span>{t("port_condition")}</span>
          <select
            value={condition}
            onChange={(e) => setCondition(normalizeCondition(e.target.value))}
          >
            {RAW_CONDITIONS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("grade_ev_fee")}</span>
          <input
            type="number"
            min={0}
            step={1}
            value={fee}
            onChange={(e) => onFeeChange(Number(e.target.value) || 0)}
          />
        </label>
        <label>
          <span>{t("grade_ev_ship")}</span>
          <input
            type="number"
            min={0}
            step={1}
            value={ship}
            onChange={(e) => onShipChange(Number(e.target.value) || 0)}
          />
        </label>
        <label>
          <span>{t("grade_ev_sell_fee")}</span>
          <input
            type="number"
            min={0}
            max={100}
            step={0.5}
            value={sellFee}
            onChange={(e) => setSellFee(Number(e.target.value) || 0)}
          />
        </label>
      </div>

      {loading ? <p className="explore-lede">{t("grade_ev_loading")}</p> : null}
      {error && !ev.ready ? <p className="form-error">{error}</p> : null}

      {!loading && !ev.ready ? (
        <p className="explore-lede">{t("grade_ev_need_psa")}</p>
      ) : null}

      {ev.ready ? (
        <>
          <div className="grade-ev-grid">
            <div className="grade-ev-metric">
              <span>{t("grade_ev_raw")}</span>
              <strong>{formatMoney(ev.raw_usd, "USD", 2)}</strong>
            </div>
            <div className="grade-ev-metric">
              <span>{t("grade_ev_psa10")}</span>
              <strong>{formatMoney(ev.psa10_usd, "USD", 2)}</strong>
            </div>
            <div className="grade-ev-metric">
              <span>{t("grade_ev_psa9")}</span>
              <strong>
                {formatMoney(ev.psa9_usd, "USD", 2)}
                {ev.psa9_source === "ratio" ? (
                  <span className="grade-ev-hint">
                    {" "}
                    (
                    {t("grade_ev_psa9_hint", {
                      pct: Math.round(ev.psa9_ratio * 100),
                    })}
                    )
                  </span>
                ) : null}
                {ev.psa9_source === "live" ? (
                  <span className="grade-ev-hint">
                    {" "}
                    ({t("grade_ev_psa9_live")})
                  </span>
                ) : null}
              </strong>
            </div>
            <div className="grade-ev-metric">
              <span>{t("grade_ev_all_in")}</span>
              <strong>{formatMoney(ev.all_in_usd, "USD", 2)}</strong>
            </div>
            <div className="grade-ev-metric">
              <span>{t("grade_ev_breakeven")}</span>
              <strong>{formatMoney(ev.breakeven_psa10_usd, "USD", 2)}</strong>
            </div>
            <div className={`grade-ev-metric grade-ev-net ${netClass}`}>
              <span>{t("grade_ev_net10")}</span>
              <strong>
                {formatMoney(ev.psa10.net_usd, "USD", 2)}
                {ev.psa10.roi_pct != null
                  ? ` · ${formatChange(ev.psa10.roi_pct, 1)}`
                  : ""}
              </strong>
            </div>
            <div className="grade-ev-metric">
              <span>{t("grade_ev_net9")}</span>
              <strong>{formatMoney(ev.psa9.net_usd, "USD", 2)}</strong>
            </div>
            <div className="grade-ev-metric">
              <span>{t("grade_ev_depth")}</span>
              <strong>
                {t("grade_ev_depth_values", {
                  s10: sales10 != null ? String(Math.round(sales10)) : "—",
                  s9: sales9 != null ? String(Math.round(sales9)) : "—",
                  window: periodKey || "—",
                })}
              </strong>
            </div>
          </div>

          <div className="grade-ev-chart-block">
            <h3>{t("grade_ev_sensitivity_title")}</h3>
            <p className="grade-ev-lede">{t("grade_ev_sensitivity_lede")}</p>
            <GradingSensitivityChart
              points={curve}
              breakevenUsd={ev.breakeven_psa10_usd}
              spotPsa10Usd={ev.psa10_usd}
              labelNet={t("grade_ev_chart_net")}
              labelExit={t("grade_ev_chart_exit")}
            />
          </div>
        </>
      ) : null}
    </section>
  );
}

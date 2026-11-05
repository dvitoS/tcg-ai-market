"use client";

import { useEffect, useMemo, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { fetchCardPriceSources, formatChange, formatMoney } from "@/lib/api";
import {
  DEFAULT_GRADE_FEE_USD,
  DEFAULT_SELL_FEE_PCT,
  DEFAULT_SHIP_USD,
  computeGradingEv,
} from "@/lib/gradingEv";
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

export function GradingEvPanel({
  cardId,
  rawPrice,
}: {
  cardId: string;
  rawPrice?: number | null;
}) {
  const { t } = useLocale();
  const [psa10, setPsa10] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [fee, setFee] = useState(DEFAULT_GRADE_FEE_USD);
  const [ship, setShip] = useState(DEFAULT_SHIP_USD);
  const [sellFee, setSellFee] = useState(DEFAULT_SELL_FEE_PCT);
  const [condition, setCondition] = useState("NM");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    void fetchCardPriceSources(cardId)
      .then((payload) => {
        if (!alive) return;
        if (payload.psa10_error) {
          setError(payload.psa10_error);
        }
        setPsa10(lastPrice(payload.psa10));
      })
      .catch((err) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : t("grade_ev_error"));
        setPsa10(null);
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
        gradeFeeUsd: fee,
        shipUsd: ship,
        sellFeePct: sellFee,
      }),
    [adjustedRaw, psa10, fee, ship, sellFee],
  );

  const netClass =
    ev.psa10.net_usd == null
      ? ""
      : ev.psa10.net_usd > 0
        ? "pnl-up"
        : ev.psa10.net_usd < 0
          ? "pnl-down"
          : "";

  return (
    <section className="grade-ev-panel" aria-label={t("grade_ev_title")}>
      <div className="detail-ai-head">
        <h2>{t("grade_ev_title")}</h2>
      </div>
      <p className="grade-ev-lede">{t("grade_ev_lede")}</p>

      <div className="grade-ev-inputs">
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
            onChange={(e) => setFee(Number(e.target.value) || 0)}
          />
        </label>
        <label>
          <span>{t("grade_ev_ship")}</span>
          <input
            type="number"
            min={0}
            step={1}
            value={ship}
            onChange={(e) => setShip(Number(e.target.value) || 0)}
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
            <strong>
              {formatMoney(ev.psa9.net_usd, "USD", 2)}
              <span className="grade-ev-hint">
                {" "}
                ({t("grade_ev_psa9_hint", { pct: Math.round(ev.psa9_ratio * 100) })})
              </span>
            </strong>
          </div>
        </div>
      ) : null}
    </section>
  );
}

"""Soft Ink AI explain rows (feature dump + confidence) for card detail."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ai_insights import explain_features, series_confidence
from trading_signals import FORECAST_DAYS, FORECAST_SIGNAL_BAND

LOG = logging.getLogger("kestrel.api.explain")


def build_card_explain(
    *,
    points: list[dict[str, Any]],
    last_price: float | None,
    predicted_price: float | None,
    pred_lo_pct: float | None = None,
    pred_hi_pct: float | None = None,
) -> dict[str, Any]:
    """Return confidence + human-readable explain rows for Soft Ink detail."""
    n = len(points)
    confidence = series_confidence(points=n, used_db_fallback=False)

    spot = float(last_price) if last_price is not None else None
    if spot is None and points:
        try:
            spot = float(points[-1]["price"])
        except (TypeError, ValueError, KeyError):
            spot = None
    predicted = float(predicted_price) if predicted_price is not None else spot

    lags: dict[str, float] = {
        "ret_1": 0.0,
        "ret_7": 0.0,
        "vol_7": 0.0,
        "dist_ma_7": 0.0,
        "set_ret_7": 0.0,
        "rel_ret_7": 0.0,
        "mean_abs_ret_7": 0.0,
        "flat_share_14": 0.0,
        "hl_range_14": 0.0,
    }
    if n >= 15 and spot is not None:
        try:
            from services.forecast import lag_features_for_last_day

            series = pd.DataFrame(
                [
                    {"date": str(p.get("date") or "")[:10], "price": float(p["price"])}
                    for p in points
                    if p.get("price") is not None
                ]
            )
            if not series.empty:
                series["date"] = pd.to_datetime(series["date"], errors="coerce")
                series = series.dropna(subset=["date", "price"]).sort_values("date")
                computed = lag_features_for_last_day(series)
                if computed:
                    lags.update({k: float(v) for k, v in computed.items() if v == v})
        except Exception as exc:
            LOG.info("lag_features_for_last_day failed: %s", exc)

    rows: list[dict[str, str]] = []
    if spot is not None and predicted is not None:
        try:
            pairs = explain_features(
                lags=lags,
                last_price=float(spot),
                predicted=float(predicted),
                hold_band=float(FORECAST_SIGNAL_BAND),
                horizon_days=int(FORECAST_DAYS),
                pred_lo_pct=pred_lo_pct,
                pred_hi_pct=pred_hi_pct,
            )
            rows = [{"label": str(k), "value": str(v)} for k, v in pairs]
        except Exception as exc:
            LOG.info("explain_features failed: %s", exc)

    return {
        "confidence_level": str(confidence.get("level") or "low"),
        "confidence_ok": bool(confidence.get("ok")),
        "confidence_reason": str(confidence.get("reason") or ""),
        "hold_band_pct": float(FORECAST_SIGNAL_BAND) * 100.0,
        "horizon_days": int(FORECAST_DAYS),
        "rows": rows,
    }

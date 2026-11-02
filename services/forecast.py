"""XGBoost prediction helpers used by detail/portfolio/scanner."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ai_xgboost import FEATURE_COLUMNS, FLAT_RET_EPS, HORIZON_DAYS, resample_daily_history
from trading_signals import FORECAST_DAYS


def card_history(history: pd.DataFrame, card_id: str) -> pd.DataFrame:
    """Daily resampling like training: mean per day, then ffill."""
    raw = history.loc[history["card_id"] == card_id].sort_values("date")
    if raw.empty:
        return raw.reset_index(drop=True)
    return resample_daily_history(raw.copy()).reset_index(drop=True)


def _feature_frame_from_prices(
    prices,
    rarity_encoded: float,
    supertype_encoded: float,
    *,
    set_ret_7: float | None = None,
) -> pd.DataFrame | None:
    values = pd.Series(prices, dtype=float).reset_index(drop=True)
    # Need enough bars for vol_7 + ma_30 + flat_share_14 / hl_range_14.
    if len(values) < 15:
        return None
    ret_1 = float(values.pct_change(1).iloc[-1])
    ret_3 = float(values.pct_change(3).iloc[-1])
    ret_7 = float(values.pct_change(7).iloc[-1]) if len(values) >= 8 else float("nan")
    daily = values.pct_change(1)
    vol_7 = float(daily.iloc[-7:].std(ddof=0)) if len(daily.dropna()) >= 7 else float("nan")
    ma_7 = float(values.iloc[-7:].mean())
    ma_30 = float(values.iloc[-min(30, len(values)) :].mean())
    spot = float(values.iloc[-1])
    if not np.isfinite(ret_1) or not np.isfinite(ret_3) or ma_7 <= 0 or ma_30 <= 0 or spot <= 0:
        return None
    if not np.isfinite(ret_7):
        ret_7 = ret_3
    if not np.isfinite(vol_7):
        vol_7 = 0.0
    abs_daily = daily.abs()
    mean_abs_ret_7 = float(abs_daily.iloc[-7:].mean())
    if not np.isfinite(mean_abs_ret_7):
        mean_abs_ret_7 = 0.0
    flat_share_14 = float((abs_daily.iloc[-14:] < FLAT_RET_EPS).mean())
    if not np.isfinite(flat_share_14):
        flat_share_14 = 0.0
    window14 = values.iloc[-14:]
    hl_mean = float(window14.mean())
    hl_range_14 = (
        float((window14.max() - window14.min()) / hl_mean) if hl_mean > 0 else 0.0
    )
    if not np.isfinite(hl_range_14):
        hl_range_14 = 0.0
    set_med = 0.0 if set_ret_7 is None or not np.isfinite(float(set_ret_7)) else float(set_ret_7)
    row = {
        "ret_1": ret_1,
        "ret_3": ret_3,
        "ret_7": ret_7,
        "vol_7": vol_7,
        "dist_ma_7": spot / ma_7 - 1.0,
        "dist_ma_30": spot / ma_30 - 1.0,
        "log_price": float(np.log(max(spot, 1e-6))),
        "set_ret_7": set_med,
        "rel_ret_7": ret_7 - set_med,
        "mean_abs_ret_7": mean_abs_ret_7,
        "flat_share_14": flat_share_14,
        "hl_range_14": hl_range_14,
        "rarity_encoded": float(rarity_encoded),
        "supertype_encoded": float(supertype_encoded),
    }
    frame = pd.DataFrame([row])[FEATURE_COLUMNS]
    if frame.isna().any(axis=None):
        return None
    return frame


def lag_features_for_last_day(series: pd.DataFrame) -> dict[str, float] | None:
    """Explainability snapshot for the detail panel (return-model features)."""
    prices = series.sort_values("date")["price"].astype(float).reset_index(drop=True)
    if len(prices) < 15:
        return None
    frame = _feature_frame_from_prices(prices, 0.0, 0.0)
    if frame is None:
        return None
    return {col: float(frame.iloc[0][col]) for col in FEATURE_COLUMNS if col in frame.columns}


def predict_horizon_return(
    model,
    prices,
    rarity_encoded: float,
    supertype_encoded: float,
    *,
    set_ret_7: float | None = None,
) -> float | None:
    """Model output: expected fractional return over HORIZON_DAYS."""
    features = _feature_frame_from_prices(
        prices, rarity_encoded, supertype_encoded, set_ret_7=set_ret_7
    )
    if features is None:
        return None
    return float(model.predict(features)[0])


def predict_from_prices(
    model,
    prices,
    rarity_encoded: float,
    supertype_encoded: float,
    *,
    set_ret_7: float | None = None,
) -> float | None:
    """Predicted price at horizon = spot × (1 + predicted return)."""
    values = pd.Series(prices, dtype=float).reset_index(drop=True)
    if values.empty:
        return None
    pred_ret = predict_horizon_return(
        model, values, rarity_encoded, supertype_encoded, set_ret_7=set_ret_7
    )
    if pred_ret is None:
        return None
    spot = float(values.iloc[-1])
    return float(spot * (1.0 + pred_ret))


def predict_next_close(
    model,
    series: pd.DataFrame,
    rarity_encoded: float,
    supertype_encoded: float,
) -> float | None:
    """Horizon target price (product default = FORECAST_DAYS, not next calendar day)."""
    prices = series.sort_values("date")["price"]
    return predict_from_prices(model, prices, rarity_encoded, supertype_encoded)


def forecast_price_in_days(
    model,
    series: pd.DataFrame,
    rarity_encoded: float,
    supertype_encoded: float,
    days: int = FORECAST_DAYS,
) -> float | None:
    """Single-shot horizon price. `days` should match training HORIZON_DAYS."""
    del days  # model is trained for HORIZON_DAYS; rolling next-day is no longer used
    prices = series.sort_values("date")["price"].astype(float)
    return predict_from_prices(model, prices, rarity_encoded, supertype_encoded)


def predicted_return_pct(
    model,
    series: pd.DataFrame,
    rarity_encoded: float,
    supertype_encoded: float,
) -> float | None:
    prices = series.sort_values("date")["price"]
    ret = predict_horizon_return(model, prices, rarity_encoded, supertype_encoded)
    return None if ret is None else float(ret * 100.0)

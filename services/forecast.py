"""XGBoost prediction helpers used by detail/portfolio/scanner."""

from __future__ import annotations

import pandas as pd

from ai_xgboost import FEATURE_COLUMNS, resample_daily_history
from trading_signals import FORECAST_DAYS


def card_history(history: pd.DataFrame, card_id: str) -> pd.DataFrame:
    """Daily resampling like training: mean per day, then ffill."""
    raw = history.loc[history["card_id"] == card_id].sort_values("date")
    if raw.empty:
        return raw.reset_index(drop=True)
    return resample_daily_history(raw.copy()).reset_index(drop=True)


def lag_features_for_last_day(series: pd.DataFrame) -> dict[str, float] | None:
    prices = series.sort_values("date")["price"].astype(float).reset_index(drop=True)
    if len(prices) < 8:
        return None
    return {
        "price_lag_1": float(prices.iloc[-2]),
        "price_lag_3": float(prices.iloc[-4]),
        "price_lag_7": float(prices.iloc[-8]),
        "rolling_mean_7": float(prices.iloc[-7:].mean()),
    }


def predict_from_prices(
    model,
    prices,
    rarity_encoded: float,
    supertype_encoded: float,
) -> float | None:
    values = pd.Series(prices, dtype=float).reset_index(drop=True)
    if len(values) < 8:
        return None
    row = {
        "price_lag_1": float(values.iloc[-2]),
        "price_lag_3": float(values.iloc[-4]),
        "price_lag_7": float(values.iloc[-8]),
        "rolling_mean_7": float(values.iloc[-7:].mean()),
        "rarity_encoded": float(rarity_encoded),
        "supertype_encoded": float(supertype_encoded),
    }
    features = pd.DataFrame([row])[FEATURE_COLUMNS]
    return float(model.predict(features)[0])


def predict_next_close(
    model,
    series: pd.DataFrame,
    rarity_encoded: float,
    supertype_encoded: float,
) -> float | None:
    prices = series.sort_values("date")["price"]
    return predict_from_prices(model, prices, rarity_encoded, supertype_encoded)


def forecast_price_in_days(
    model,
    series: pd.DataFrame,
    rarity_encoded: float,
    supertype_encoded: float,
    days: int = FORECAST_DAYS,
) -> float | None:
    prices = series.sort_values("date")["price"].astype(float).tolist()
    for _ in range(days):
        nxt = predict_from_prices(model, prices, rarity_encoded, supertype_encoded)
        if nxt is None:
            return None
        prices.append(max(nxt, 0.0))
    return prices[-1]

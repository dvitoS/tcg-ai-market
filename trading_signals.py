"""Trading signal helpers shared by app UI and charts."""

from __future__ import annotations

import numpy as np
import pandas as pd

HOLD_BAND = 0.0035  # legacy tight band (detail micro-move UI)
FORECAST_DAYS = 7
# Signal band for 7d forward-return model (competitors often use ±5% on 30d).
FORECAST_SIGNAL_BAND = 0.02
SCANNER_GROWTH_FLOOR = 10.0

SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_HOLD = "HOLD"
SIGNAL_CLASS = {
    SIGNAL_BUY: "signal-buy",
    SIGNAL_SELL: "signal-sell",
    SIGNAL_HOLD: "signal-hold",
}


def trading_signal(
    current_price: float,
    predicted_price: float,
    *,
    band: float | None = None,
) -> str:
    if current_price <= 0:
        return SIGNAL_HOLD
    threshold = float(FORECAST_SIGNAL_BAND if band is None else band)
    change = (predicted_price - current_price) / current_price
    if change > threshold:
        return SIGNAL_BUY
    if change < -threshold:
        return SIGNAL_SELL
    return SIGNAL_HOLD


def assign_signals(quotes: pd.DataFrame) -> pd.DataFrame:
    """Attach expected move + BUY/SELL/HOLD using the forecast-horizon band."""
    board = quotes.copy()
    price = pd.to_numeric(board["price"], errors="coerce")
    predicted = pd.to_numeric(board["predicted_price"], errors="coerce")
    board["expected_change_pct"] = np.where(
        price > 0, (predicted - price) / price * 100.0, 0.0
    )
    board["signal"] = [
        trading_signal(float(c), float(p))
        if c is not None and p is not None and not pd.isna(c) and not pd.isna(p)
        else SIGNAL_HOLD
        for c, p in zip(price.tolist(), predicted.tolist(), strict=True)
    ]
    return board

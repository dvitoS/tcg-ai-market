"""Trading signal helpers shared by app UI and charts."""

from __future__ import annotations

import pandas as pd

HOLD_BAND = 0.0035
FORECAST_DAYS = 7
SCANNER_GROWTH_FLOOR = 10.0

SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_HOLD = "HOLD"
SIGNAL_CLASS = {
    SIGNAL_BUY: "signal-buy",
    SIGNAL_SELL: "signal-sell",
    SIGNAL_HOLD: "signal-hold",
}


def trading_signal(current_price: float, predicted_price: float) -> str:
    if current_price <= 0:
        return SIGNAL_HOLD
    change = (predicted_price - current_price) / current_price
    if change > HOLD_BAND:
        return SIGNAL_BUY
    if change < -HOLD_BAND:
        return SIGNAL_SELL
    return SIGNAL_HOLD


def assign_signals(quotes: pd.DataFrame) -> pd.DataFrame:
    board = quotes.copy()
    board["expected_change_pct"] = (
        (board["predicted_price"] - board["price"]) / board["price"] * 100.0
    )
    board["signal"] = [
        trading_signal(float(current), float(predicted))
        for current, predicted in zip(board["price"], board["predicted_price"], strict=True)
    ]
    return board

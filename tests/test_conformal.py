"""Split conformal intervals and BUY/SELL gating."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ai_xgboost import CONFORMAL_WIDTH_CAP, card_forecasts, conformal_abs_quantile
from trading_signals import SIGNAL_BUY, SIGNAL_HOLD, apply_conformal_gate, assign_signals


def test_conformal_quantile_finite_sample():
    residuals = np.array([0.01, -0.02, 0.03, -0.04, 0.05, 0.0, 0.02])
    q = conformal_abs_quantile(residuals, alpha=0.2)
    assert q == q and q > 0
    assert q <= float(np.max(np.abs(residuals))) + 1e-9


def test_apply_conformal_gate_holds_when_interval_crosses_zero():
    board = pd.DataFrame(
        [
            {
                "id": "a",
                "price": 100.0,
                "predicted_price": 106.0,
                "conformal_ok": False,
                "signal": SIGNAL_BUY,
            },
            {
                "id": "b",
                "price": 100.0,
                "predicted_price": 106.0,
                "conformal_ok": True,
                "signal": SIGNAL_BUY,
            },
        ]
    )
    out = apply_conformal_gate(board)
    assert out.loc[0, "signal"] == SIGNAL_HOLD
    assert out.loc[1, "signal"] == SIGNAL_BUY


def test_assign_signals_respects_conformal_ok():
    board = pd.DataFrame(
        [
            {
                "id": "1",
                "price": 100.0,
                "predicted_price": 105.0,
                "conformal_ok": False,
            }
        ]
    )
    out = assign_signals(board)
    assert out.loc[0, "signal"] == SIGNAL_HOLD


def test_card_forecasts_marks_cross_zero_uncertain(monkeypatch):
    featured = pd.DataFrame(
        [
            {
                "card_id": "c1",
                "date": pd.Timestamp("2024-02-01"),
                "price": 10.0,
                "market_price": 10.0,
                "name": "C",
                "rarity": "Rare",
                "supertype": "Pokémon",
                "set_name": "S",
                "ret_1": 0.0,
                "ret_3": 0.0,
                "ret_7": 0.0,
                "vol_7": 0.01,
                "dist_ma_7": 0.0,
                "dist_ma_30": 0.0,
                "log_price": np.log(10.0),
                "set_ret_7": 0.0,
                "rel_ret_7": 0.0,
                "mean_abs_ret_7": 0.01,
                "flat_share_14": 0.2,
                "hl_range_14": 0.05,
                "ebay_active_n_log": 0.0,
                "ebay_ask_premium": 0.0,
                "ebay_has_obs": 0.0,
                "rarity_encoded": 1.0,
                "supertype_encoded": 0.0,
            }
        ]
    )

    class _M:
        def predict(self, X):
            # Small positive point estimate; wide q will cross zero.
            return np.full(len(X), 0.03)

    out = card_forecasts(_M(), featured, conformal_q=0.08)
    assert float(out.loc[0, "pred_lo_pct"]) < 0
    assert float(out.loc[0, "pred_hi_pct"]) > 0
    assert bool(out.loc[0, "conformal_ok"]) is False

    out2 = card_forecasts(_M(), featured, conformal_q=0.01)
    assert bool(out2.loc[0, "conformal_ok"]) is True
    assert float(out2.loc[0, "pred_hi"] - out2.loc[0, "pred_lo"]) <= CONFORMAL_WIDTH_CAP

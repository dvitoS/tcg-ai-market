"""Expanding-window walk-forward helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ai_xgboost import FEATURE_COLUMNS
from services.walk_forward import (
    _fold_date_bounds,
    score_fold_predictions,
    walk_forward_evaluate,
    walk_forward_summary_metrics,
)


def test_fold_date_bounds_expanding():
    dates = pd.date_range("2024-01-01", periods=20, freq="D").to_numpy()
    bounds = _fold_date_bounds(dates, n_folds=4, min_train_frac=0.4)
    assert len(bounds) == 4
    # Contiguous non-overlapping windows, expanding train implied by starts rising.
    for i in range(1, len(bounds)):
        assert bounds[i][0] >= bounds[i - 1][0]
        assert bounds[i - 1][1] <= bounds[i][0] or bounds[i - 1][1] == bounds[i][0]


def test_score_fold_perfect_direction():
    y = np.array([0.05, -0.05, 0.08, -0.01])
    pred = np.array([0.04, -0.06, 0.07, 0.0])
    scored = score_fold_predictions(y, pred, hold_band=0.02)
    assert scored["direction_n"] == 3.0  # last is flat actual within band? -0.01 < 0.02 → flat
    assert scored["direction_accuracy_pct"] == 100.0
    assert scored["rmse_vs_naive"] < 1.0


def _synthetic_trainable(n_days: int = 60, n_cards: int = 8) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = []
    for card_i in range(n_cards):
        price = 10.0 + card_i
        for d in pd.date_range("2024-01-01", periods=n_days, freq="D"):
            shock = float(rng.normal(0, 0.02))
            # Mild momentum so the model has something to fit.
            ret_1 = shock
            target = shock * 0.6 + float(rng.normal(0, 0.01))
            price *= 1.0 + shock
            row = {
                "card_id": f"c{card_i}",
                "date": d,
                "price": price,
                "target_return": target,
                "ret_1": ret_1,
                "ret_3": ret_1,
                "ret_7": ret_1,
                "vol_7": abs(ret_1) + 0.01,
                "dist_ma_7": ret_1,
                "dist_ma_30": ret_1 * 0.5,
                "log_price": float(np.log(max(price, 0.01))),
                "set_ret_7": ret_1 * 0.3,
                "rel_ret_7": ret_1 * 0.7,
                "mean_abs_ret_7": abs(ret_1),
                "flat_share_14": 0.2,
                "hl_range_14": abs(ret_1) * 2,
                "ebay_active_n_log": 0.0,
                "ebay_ask_premium": 0.0,
                "ebay_has_obs": 0.0,
                "rarity_encoded": card_i % 3,
                "supertype_encoded": 0,
            }
            rows.append(row)
    frame = pd.DataFrame(rows)
    assert set(FEATURE_COLUMNS).issubset(frame.columns)
    return frame


def test_walk_forward_runs_on_synthetic():
    df = _synthetic_trainable()
    result = walk_forward_evaluate(
        df,
        n_folds=3,
        min_train_rows=40,
        min_test_rows=10,
        min_train_frac=0.35,
        quiet=True,
    )
    assert result["wf_skipped"] is False
    assert int(result["wf_folds"]) >= 1
    summary = walk_forward_summary_metrics(result)
    assert summary["wf_folds"] >= 1
    assert "wf_rmse_vs_naive" in summary


def test_walk_forward_skips_short_history():
    df = _synthetic_trainable(n_days=5, n_cards=2)
    result = walk_forward_evaluate(df, n_folds=4, quiet=True)
    assert result["wf_skipped"] is True
    assert walk_forward_summary_metrics(result) == {"wf_folds": 0}

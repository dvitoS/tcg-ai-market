"""Direction / naive-baseline evaluation for next-day price models."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ai_xgboost import _signed_move, evaluate_model


class _ConstModel:
    """Predict a constant absolute price (persistence-like when equal to spot)."""

    def __init__(self, value: float):
        self.value = float(value)

    def predict(self, X):
        return np.full(len(X), self.value, dtype=float)


def test_signed_move_hold_band():
    spot = np.array([100.0, 100.0, 100.0])
    future = np.array([100.2, 101.0, 99.0])  # +0.2%, +1%, -1%
    dirs = _signed_move(future, spot, hold_band=0.0035)
    assert list(dirs) == [0, 1, -1]


def test_evaluate_detects_persistence_trap():
    # Spot always 100; true next day oscillates; model always predicts 100.
    n = 40
    X = pd.DataFrame({"price_lag_1": np.full(n, 100.0)})
    spot = pd.Series(np.full(n, 100.0))
    y = pd.Series(np.where(np.arange(n) % 2 == 0, 102.0, 98.0))
    metrics = evaluate_model(_ConstModel(100.0), X, y, spot=spot, hold_band=0.0035)
    assert metrics["rmse"] > 0
    assert metrics["naive_rmse"] == metrics["rmse"]
    assert abs(metrics["rmse_vs_naive"] - 1.0) < 1e-9
    assert metrics["pred_flat_pct"] == 100.0
    # Actual moves are ±2% every day → model never gets direction right.
    assert metrics["direction_accuracy_pct"] == 0.0

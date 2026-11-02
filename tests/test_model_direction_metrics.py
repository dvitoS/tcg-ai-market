"""Direction / naive-baseline evaluation for forward-return models."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ai_xgboost import _signed_return, evaluate_model


class _ConstReturnModel:
    def __init__(self, value: float):
        self.value = float(value)

    def predict(self, X):
        return np.full(len(X), self.value, dtype=float)


def test_signed_return_hold_band():
    rets = np.array([0.01, 0.05, -0.05])
    dirs = _signed_return(rets, hold_band=0.02)
    assert list(dirs) == [0, 1, -1]


def test_evaluate_return_model_vs_zero_baseline():
    n = 40
    X = pd.DataFrame({"ret_1": np.zeros(n)})
    # Actual returns alternate ±5%; model always predicts 0% (naive).
    y = pd.Series(np.where(np.arange(n) % 2 == 0, 0.05, -0.05))
    metrics = evaluate_model(
        _ConstReturnModel(0.0),
        X,
        y,
        target_kind="return",
        hold_band=0.02,
    )
    assert metrics["rmse"] > 0
    assert abs(metrics["rmse_vs_naive"] - 1.0) < 1e-9
    assert metrics["pred_flat_pct"] == 100.0
    assert metrics["direction_accuracy_pct"] == 0.0


def test_feature_row_builds_for_horizon_predict():
    from services.forecast import predict_from_prices

    class _Model:
        def predict(self, X):
            assert "ret_1" in X.columns
            assert "dist_ma_30" in X.columns
            return np.array([0.10])  # +10%

    prices = list(np.linspace(10.0, 12.0, 40))
    pred = predict_from_prices(_Model(), prices, 1.0, 0.0)
    assert pred is not None
    assert abs(pred - 12.0 * 1.10) < 1e-6

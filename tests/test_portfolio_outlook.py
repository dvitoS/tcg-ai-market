"""Portfolio-native 30d outlook helpers."""

from __future__ import annotations

import pandas as pd

from services.portfolio_outlook import (
    ACTION_ADD,
    ACTION_HOLD,
    ACTION_TRIM,
    enrich_portfolio_outlook,
    lot_action,
)


def test_lot_action_gates_and_thresholds():
    assert lot_action(expected_pct=12.0, conformal_ok=True) == ACTION_ADD
    assert lot_action(expected_pct=-12.0, conformal_ok=True) == ACTION_TRIM
    assert lot_action(expected_pct=12.0, conformal_ok=False) == ACTION_HOLD
    assert lot_action(expected_pct=1.0, conformal_ok=True) == ACTION_HOLD


def test_enrich_empty_view():
    view = pd.DataFrame(
        columns=[
            "card_id",
            "quantity",
            "current_price",
            "rarity_encoded",
            "supertype_encoded",
        ]
    )
    out, info = enrich_portfolio_outlook(view, pd.DataFrame())
    assert out.empty
    assert "outlook_price" in out.columns
    assert info["horizon_days"] == 30


def test_enrich_fallback_without_30d_model(monkeypatch):
    import services.portfolio_outlook as po

    monkeypatch.setattr(po, "load_portfolio_model", lambda: None)

    view = pd.DataFrame(
        [
            {
                "card_id": "c1",
                "quantity": 2,
                "current_price": 10.0,
                "rarity_encoded": 1.0,
                "supertype_encoded": 0.0,
            }
        ]
    )
    history = pd.DataFrame(
        [
            {
                "card_id": "c1",
                "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=i),
                "price": 10.0 + i * 0.01,
                "name": "C",
                "rarity": "Rare",
                "supertype": "Pokémon",
                "set_name": "S",
                "market_price": 10.0,
            }
            for i in range(40)
        ]
    )

    class _M:
        def predict(self, X):
            import numpy as np

            return np.full(len(X), 0.10)

    out, info = enrich_portfolio_outlook(view, history, fallback_model=_M())
    assert info["using_30d"] is False
    assert float(out.loc[0, "outlook_roi_pct"]) == 10.0
    assert float(out.loc[0, "outlook_value"]) == 22.0

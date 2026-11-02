"""Set-relative features and forecast-horizon signal band."""

from __future__ import annotations

import pandas as pd

from ai_xgboost import FEATURE_COLUMNS, add_time_features
from trading_signals import FORECAST_SIGNAL_BAND, SIGNAL_BUY, SIGNAL_HOLD, assign_signals, trading_signal


def test_set_relative_features_on_panel():
    rows = []
    for day in range(40):
        date = pd.Timestamp("2024-01-01") + pd.Timedelta(days=day)
        # Card A flat; card B rising with the set.
        rows.append(
            {
                "card_id": "a",
                "date": date,
                "price": 10.0,
                "name": "A",
                "rarity": "Rare",
                "supertype": "Pokémon",
                "set_name": "SetX",
                "market_price": 10.0,
            }
        )
        rows.append(
            {
                "card_id": "b",
                "date": date,
                "price": 10.0 * (1.01**day),
                "name": "B",
                "rarity": "Rare",
                "supertype": "Pokémon",
                "set_name": "SetX",
                "market_price": 10.0,
            }
        )
    featured, _ = add_time_features(pd.DataFrame(rows))
    assert "set_ret_7" in featured.columns
    assert "rel_ret_7" in featured.columns
    assert "set_ret_7" in FEATURE_COLUMNS
    for col in ("mean_abs_ret_7", "flat_share_14", "hl_range_14"):
        assert col in featured.columns
        assert col in FEATURE_COLUMNS
    latest = featured.sort_values("date").groupby("card_id").tail(1).set_index("card_id")
    # Flat card should lag a rising set → negative relative return.
    assert float(latest.loc["a", "rel_ret_7"]) < 0
    assert float(latest.loc["b", "rel_ret_7"]) >= float(latest.loc["a", "rel_ret_7"])
    # Flat card → high flat share; rising card → more activity / range.
    assert float(latest.loc["a", "flat_share_14"]) > float(latest.loc["b", "flat_share_14"])
    assert float(latest.loc["b", "mean_abs_ret_7"]) > float(latest.loc["a", "mean_abs_ret_7"])
    assert float(latest.loc["b", "hl_range_14"]) > float(latest.loc["a", "hl_range_14"])


def test_forecast_signal_band_is_wider_than_noise():
    assert FORECAST_SIGNAL_BAND >= 0.02
    assert trading_signal(100.0, 101.0) == SIGNAL_HOLD  # +1%
    assert trading_signal(100.0, 103.0) == SIGNAL_BUY  # +3%


def test_assign_signals_uses_horizon_band():
    board = pd.DataFrame(
        [
            {"id": "1", "price": 100.0, "predicted_price": 101.0},
            {"id": "2", "price": 100.0, "predicted_price": 105.0},
        ]
    )
    out = assign_signals(board)
    assert out.loc[0, "signal"] == SIGNAL_HOLD
    assert out.loc[1, "signal"] == SIGNAL_BUY

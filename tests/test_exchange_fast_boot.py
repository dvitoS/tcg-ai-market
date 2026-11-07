"""Fast-boot path must attach encodings and refuse bad model feature sets."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from ai_xgboost import FEATURE_COLUMNS


def test_try_fast_boot_attaches_encodings_from_maps(monkeypatch):
    import services.exchange as exchange

    quotes = pd.DataFrame(
        [
            {
                "id": "c1",
                "name": "A",
                "rarity": "Rare",
                "supertype": "Pokémon",
                "price": 5.0,
                "market_price": 5.0,
            }
        ]
    )
    history = pd.DataFrame(
        [
            {
                "card_id": "c1",
                "date": pd.Timestamp("2024-01-01"),
                "price": 5.0,
                "name": "A",
                "rarity": "Rare",
                "supertype": "Pokémon",
                "set_name": "S",
                "market_price": 5.0,
            }
        ]
    )
    meta = {
        "feature_columns": list(FEATURE_COLUMNS),
        "trained_at": "2024-01-01",
        "metrics": {
            "label_maps": {
                "rarity": {"Rare": 2},
                "supertype": {"Pokémon": 0},
            }
        },
    }

    monkeypatch.setattr(
        "services.quotes_store.load_market_quotes", lambda: quotes
    )
    monkeypatch.setattr(
        "services.model_store.load_model_artifact",
        lambda: (MagicMock(name="model"), meta),
    )
    monkeypatch.setattr(exchange, "load_history", lambda **kwargs: history)
    monkeypatch.setattr(exchange, "_filter_catalog_floor", lambda q: q)

    result = exchange._try_fast_boot()
    assert result is not None
    _hist, board, _model = result
    assert "rarity_encoded" in board.columns
    assert float(board.loc[0, "rarity_encoded"]) == 2.0


def test_try_fast_boot_skips_on_feature_mismatch(monkeypatch):
    import services.exchange as exchange

    monkeypatch.setattr(
        "services.quotes_store.load_market_quotes",
        lambda: pd.DataFrame([{"id": "c1", "name": "A", "price": 1.0}]),
    )
    monkeypatch.setattr(
        "services.model_store.load_model_artifact",
        lambda: (
            MagicMock(),
            {"feature_columns": ["price_lag_1"], "trained_at": "x", "metrics": {}},
        ),
    )
    assert exchange._try_fast_boot() is None


def test_attach_price_change_7d_from_history():
    import services.exchange as exchange

    quotes = pd.DataFrame([{"id": "c1", "name": "A", "price": 10.0}])
    history = pd.DataFrame(
        [
            {"card_id": "c1", "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=i), "price": 8.0 + i * 0.25}
            for i in range(10)
        ]
    )
    out = exchange.attach_price_change_7d(quotes, history)
    assert "price_change_7d_pct" in out.columns
    assert pd.notna(out.loc[0, "price_change_7d_pct"])
    assert "price_change_3d_pct" in out.columns
    assert pd.notna(out.loc[0, "price_change_3d_pct"])


def test_attach_expected_change_30d_without_model(monkeypatch):
    import services.exchange as exchange

    monkeypatch.setattr(
        "services.portfolio_outlook.load_portfolio_model",
        lambda: None,
    )
    quotes = pd.DataFrame(
        [{"id": "c1", "name": "A", "price": 10.0, "expected_change_pct": 1.2}]
    )
    featured = pd.DataFrame(
        [
            {
                "card_id": "c1",
                "date": pd.Timestamp("2024-01-01"),
                "price": 10.0,
                "name": "A",
            }
        ]
    )
    out = exchange.attach_expected_change_30d(quotes, featured)
    assert "expected_change_30d_pct" in out.columns
    assert pd.isna(out.loc[0, "expected_change_30d_pct"])


def test_attach_expected_change_30d_from_forecasts(monkeypatch):
    import services.exchange as exchange

    class _Model:
        pass

    monkeypatch.setattr(
        "services.portfolio_outlook.load_portfolio_model",
        lambda: (_Model(), {"metrics": {"conformal_q": 0.1, "horizon_days": 30}}),
    )
    monkeypatch.setattr(
        exchange,
        "card_forecasts",
        lambda *_a, **_k: pd.DataFrame(
            [{"id": "c1", "expected_change_pct": 12.5}]
        ),
    )
    quotes = pd.DataFrame(
        [{"id": "c1", "name": "A", "price": 10.0, "expected_change_pct": 1.2}]
    )
    featured = pd.DataFrame(
        [{"card_id": "c1", "date": pd.Timestamp("2024-01-01"), "price": 10.0}]
    )
    out = exchange.attach_expected_change_30d(quotes, featured)
    assert float(out.loc[0, "expected_change_30d_pct"]) == 12.5
    # Board 7d signal field stays untouched.
    assert float(out.loc[0, "expected_change_pct"]) == 1.2

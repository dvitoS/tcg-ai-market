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

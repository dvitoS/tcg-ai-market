"""Unit tests for market_quotes row mapping."""

from __future__ import annotations

import pandas as pd

from services.quotes_store import _rows_from_quotes


def test_rows_from_quotes_maps_id_and_defaults():
    quotes = pd.DataFrame(
        [
            {
                "id": "sv3-1",
                "name": "Pikachu",
                "set_name": "151",
                "rarity": "Rare",
                "supertype": "Pokémon",
                "price": 12.5,
                "market_price": 12.0,
                "predicted_price": 13.0,
                "expected_change_pct": 4.0,
                "signal": "BUY",
                "confidence_ok": True,
                "confidence_level": "high",
                "history_points": 30,
            }
        ]
    )
    rows = _rows_from_quotes(quotes)
    assert len(rows) == 1
    assert rows[0]["card_id"] == "sv3-1"
    assert rows[0]["signal"] == "BUY"
    assert rows[0]["confidence_ok"] is True
    assert rows[0]["history_points"] == 30

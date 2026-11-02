"""Unit tests for market_quotes row mapping."""

from __future__ import annotations

import pandas as pd

from ai_xgboost import apply_label_maps
from services.exchange import ensure_quote_encodings
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
                "rarity_encoded": 3.0,
                "supertype_encoded": 1.0,
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
    assert rows[0]["rarity_encoded"] == 3.0
    assert rows[0]["supertype_encoded"] == 1.0


def test_ensure_quote_encodings_from_label_maps():
    quotes = pd.DataFrame(
        [
            {
                "id": "sv3-1",
                "name": "Pikachu",
                "rarity": "Rare",
                "supertype": "Pokémon",
                "price": 1.0,
            }
        ]
    )
    meta = {
        "metrics": {
            "label_maps": {
                "rarity": {"Common": 0, "Rare": 1},
                "supertype": {"Pokémon": 0, "Trainer": 1},
            }
        }
    }
    out = ensure_quote_encodings(quotes, meta=meta)
    assert float(out.loc[0, "rarity_encoded"]) == 1.0
    assert float(out.loc[0, "supertype_encoded"]) == 0.0


def test_apply_label_maps_unknown_is_nan():
    frame = pd.DataFrame([{"rarity": "Mythic", "supertype": "Pokémon"}])
    out = apply_label_maps(
        frame,
        {"rarity": {"Rare": 1}, "supertype": {"Pokémon": 0}},
    )
    assert pd.isna(out.loc[0, "rarity_encoded"])
    assert float(out.loc[0, "supertype_encoded"]) == 0.0

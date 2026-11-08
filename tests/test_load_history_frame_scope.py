"""price_history loads must stay scoped — full-table fetch_all times out."""

from __future__ import annotations

import pandas as pd

import database_catalog as catalog


def test_load_history_frame_embed_path(monkeypatch):
    monkeypatch.setattr(
        catalog,
        "_fetch_price_history_rows",
        lambda **kwargs: [
            {
                "card_id": "base1-1",
                "price": 10.0,
                "date": "2026-11-01",
                "cards": {
                    "name": "Alakazam",
                    "supertype": "Pokémon",
                    "rarity": "Rare Holo",
                    "set_name": "Base",
                    "market_price": 12.0,
                },
            }
        ],
    )
    df = catalog.load_history_frame(since_date="2026-10-01")
    assert list(df["card_id"]) == ["base1-1"]
    assert float(df.iloc[0]["price"]) == 10.0


def test_load_history_frame_fallback_never_calls_fetch_all_history(monkeypatch):
    calls: list[tuple] = []

    def boom_embed(**kwargs):
        if kwargs.get("embed_cards", True):
            raise RuntimeError("embed broken")
        calls.append(("plain", kwargs.get("since_date"), kwargs.get("card_ids")))
        return [
            {"card_id": "sv1-1", "price": 1.5, "date": "2026-11-02"},
        ]

    def forbid_fetch_all(table, columns="*", *, order=None):
        if table == "price_history":
            raise AssertionError("must not fetch_all price_history")
        if table == "cards":
            return [
                {
                    "id": "sv1-1",
                    "name": "Sprigatito",
                    "supertype": "Pokémon",
                    "rarity": "Common",
                    "set_name": "SV",
                    "market_price": 1.0,
                }
            ]
        return []

    monkeypatch.setattr(catalog, "_fetch_price_history_rows", boom_embed)
    monkeypatch.setattr(catalog, "fetch_all", forbid_fetch_all)

    df = catalog.load_history_frame(since_date="2026-10-01")
    assert not df.empty
    assert list(df["card_id"]) == ["sv1-1"]
    assert calls == [("plain", "2026-10-01", None)]


def test_retrain_ai_passes_since_date(monkeypatch):
    import ai_xgboost
    import nightly_update as nu
    import services.exchange as exchange

    captured: dict = {}
    hist = pd.DataFrame(
        {
            "card_id": ["a"],
            "price": [1.0],
            "date": [pd.Timestamp("2026-11-01")],
            "name": ["A"],
            "supertype": ["Pokémon"],
            "rarity": ["Common"],
            "set_name": ["S"],
            "market_price": [1.0],
        }
    )

    def fake_load_history(**kwargs):
        captured.update(kwargs)
        return hist

    monkeypatch.setattr(ai_xgboost, "load_history", fake_load_history)
    monkeypatch.setattr(
        ai_xgboost,
        "retrain_model",
        lambda **kwargs: {"cards": 1, "rows": 1, "rmse": 0.1, "r2": 0.5},
    )
    monkeypatch.setattr(
        exchange,
        "build_market_board",
        lambda **kwargs: (None, pd.DataFrame({"id": ["a"]}), None),
    )

    metrics = nu.retrain_ai()
    assert captured.get("since_date")
    assert metrics.get("quotes") == 1

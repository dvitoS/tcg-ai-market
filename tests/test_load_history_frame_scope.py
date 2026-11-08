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


def test_history_id_chunks_empty_means_no_queries():
    assert catalog._history_id_chunks(None) == []
    assert catalog._history_id_chunks([]) == []
    assert catalog._history_id_chunks(["a", "b"]) == [["a", "b"]]


def test_fetch_price_history_rows_auto_chunks_catalog_ids(monkeypatch):
    """Unscoped loads must not date-scan the whole table (nightly 57014)."""
    seen_in_filters: list[list[str]] = []

    class _FakeQuery:
        def __init__(self):
            self._in: list[str] | None = None

        def select(self, *_a, **_k):
            return self

        def in_(self, _col, values):
            self._in = list(values)
            seen_in_filters.append(list(values))
            return self

        def gte(self, *_a, **_k):
            return self

        def order(self, *_a, **_k):
            return self

        def range(self, *_a, **_k):
            return self

        def execute(self):
            ids = self._in or []
            return type(
                "R",
                (),
                {
                    "data": [
                        {"card_id": cid, "price": 1.0, "date": "2026-11-01"}
                        for cid in ids
                    ]
                },
            )()

    class _FakeTable:
        def select(self, *_a, **_k):
            return _FakeQuery().select()

    class _FakeClient:
        def table(self, _name):
            return _FakeTable()

    catalog_ids = [f"c{i}" for i in range(320)]  # → 3 chunks of 150/150/20

    monkeypatch.setattr(catalog, "get_supabase", lambda: _FakeClient())
    monkeypatch.setattr(
        catalog,
        "fetch_all",
        lambda table, columns="*", **_k: (
            [{"id": cid} for cid in catalog_ids] if table == "cards" else []
        ),
    )

    rows = catalog._fetch_price_history_rows(
        card_ids=None, since_date="2026-07-20", embed_cards=False
    )
    assert len(seen_in_filters) == 3
    assert seen_in_filters[0] == catalog_ids[:150]
    assert seen_in_filters[1] == catalog_ids[150:300]
    assert seen_in_filters[2] == catalog_ids[300:]
    assert len(rows) == 320
    assert {r["card_id"] for r in rows} == set(catalog_ids)


def test_load_history_defaults_since_when_unscoped(monkeypatch):
    import ai_xgboost as ax

    captured: dict = {}

    monkeypatch.setattr(
        ax,
        "load_history_frame",
        lambda **kwargs: (
            captured.update(kwargs)
            or pd.DataFrame(
                {
                    "card_id": ["a"],
                    "price": [1.0],
                    "date": ["2026-11-01"],
                    "name": ["A"],
                    "supertype": ["Pokémon"],
                    "rarity": ["Common"],
                    "set_name": ["S"],
                    "market_price": [1.0],
                }
            )
        ),
    )
    monkeypatch.setattr(ax, "resample_daily_history", lambda df: df)

    ax.load_history()
    assert captured.get("since_date")
    assert captured.get("card_ids") is None


def test_load_history_skips_default_since_when_card_ids(monkeypatch):
    import ai_xgboost as ax

    captured: dict = {}

    monkeypatch.setattr(
        ax,
        "load_history_frame",
        lambda **kwargs: (
            captured.update(kwargs)
            or pd.DataFrame(
                {
                    "card_id": ["a"],
                    "price": [1.0],
                    "date": ["2026-11-01"],
                    "name": ["A"],
                    "supertype": ["Pokémon"],
                    "rarity": ["Common"],
                    "set_name": ["S"],
                    "market_price": [1.0],
                }
            )
        ),
    )
    monkeypatch.setattr(ax, "resample_daily_history", lambda df: df)

    ax.load_history(card_ids=["a"])
    assert captured.get("card_ids") == ["a"]
    assert captured.get("since_date") is None


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

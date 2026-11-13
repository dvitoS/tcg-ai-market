"""Hot-desk JustTCG drip priority (Radar + watchlist before missing history)."""

from __future__ import annotations

from database_clients import Card
from database_catalog import list_cards_for_sync


def _card(cid: str, price: float | None = 10.0) -> Card:
    return Card(id=cid, name=cid, market_price=price)


def test_list_cards_for_sync_hot_desk_before_missing_history(monkeypatch) -> None:
    cards = [
        _card("miss-a", 50.0),
        _card("hot-cheap", 5.0),
        _card("have-b", 100.0),
        _card("hot-miss", 8.0),
    ]
    monkeypatch.setattr(
        "database_catalog.list_cards",
        lambda limit=None, order_price_desc=False: list(cards),
    )
    monkeypatch.setattr(
        "database_catalog.distinct_history_card_ids",
        lambda: {"have-b", "hot-cheap"},
    )
    monkeypatch.setattr("database_catalog.hot_desk_sync_enabled", lambda: True)
    monkeypatch.setattr(
        "database_catalog.hot_desk_card_ids",
        lambda limit=None: {"hot-cheap", "hot-miss"},
    )
    # Non-bulk on/off must not reorder ahead of hot desk.
    monkeypatch.setattr("database_catalog.nonbulk_sync_priority_enabled", lambda: True)
    monkeypatch.setattr("database_catalog.bulk_sync_max_usd", lambda: 2.0)

    ordered = list_cards_for_sync(limit=4)
    assert [c.id for c in ordered] == ["hot-miss", "hot-cheap", "miss-a", "have-b"]


def test_list_cards_for_sync_can_disable_hot_desk(monkeypatch) -> None:
    cards = [
        _card("miss-a", 50.0),
        _card("hot-cheap", 5.0),
        _card("have-b", 100.0),
    ]
    monkeypatch.setattr(
        "database_catalog.list_cards",
        lambda limit=None, order_price_desc=False: list(cards),
    )
    monkeypatch.setattr(
        "database_catalog.distinct_history_card_ids",
        lambda: {"have-b", "hot-cheap"},
    )
    monkeypatch.setattr("database_catalog.hot_desk_sync_enabled", lambda: False)
    monkeypatch.setattr("database_catalog.nonbulk_sync_priority_enabled", lambda: True)
    monkeypatch.setattr("database_catalog.bulk_sync_max_usd", lambda: 2.0)

    ordered = list_cards_for_sync(limit=3)
    assert [c.id for c in ordered] == ["miss-a", "have-b", "hot-cheap"]


def test_list_cards_for_sync_nonbulk_before_missing_bulk(monkeypatch) -> None:
    """Chase with history should refresh before a missing-history $0.25 common."""
    cards = [
        _card("miss-bulk", 0.25),
        _card("have-chase", 80.0),
        _card("miss-mid", 5.0),
        _card("hot-x", 1.0),
    ]
    monkeypatch.setattr(
        "database_catalog.list_cards",
        lambda limit=None, order_price_desc=False: list(cards),
    )
    monkeypatch.setattr(
        "database_catalog.distinct_history_card_ids",
        lambda: {"have-chase", "hot-x"},
    )
    monkeypatch.setattr("database_catalog.hot_desk_sync_enabled", lambda: True)
    monkeypatch.setattr(
        "database_catalog.hot_desk_card_ids",
        lambda limit=None: {"hot-x"},
    )
    monkeypatch.setattr("database_catalog.nonbulk_sync_priority_enabled", lambda: True)
    monkeypatch.setattr("database_catalog.bulk_sync_max_usd", lambda: 2.0)

    ordered = list_cards_for_sync(limit=4)
    assert [c.id for c in ordered] == [
        "hot-x",
        "miss-mid",
        "have-chase",
        "miss-bulk",
    ]


def test_list_cards_for_sync_nonbulk_kill_switch_restores_old_order(monkeypatch) -> None:
    cards = [
        _card("miss-bulk", 0.25),
        _card("have-chase", 80.0),
    ]
    monkeypatch.setattr(
        "database_catalog.list_cards",
        lambda limit=None, order_price_desc=False: list(cards),
    )
    monkeypatch.setattr(
        "database_catalog.distinct_history_card_ids",
        lambda: {"have-chase"},
    )
    monkeypatch.setattr("database_catalog.hot_desk_sync_enabled", lambda: False)
    monkeypatch.setattr("database_catalog.nonbulk_sync_priority_enabled", lambda: False)

    ordered = list_cards_for_sync(limit=2)
    # Old ranking: missing history before have-history, even if bulk.
    assert [c.id for c in ordered] == ["miss-bulk", "have-chase"]


def test_hot_desk_card_ids_merges_watchlist_and_quotes(monkeypatch) -> None:
    import pandas as pd

    import database_catalog as dc

    class _FakeTable:
        def __init__(self, rows):
            self._rows = rows
            self._signal = None
            self._desc = None
            self._limit = None

        def select(self, *_a, **_k):
            return self

        def eq(self, key, value):
            if key == "signal":
                self._signal = value
            return self

        def order(self, _col, desc=False):
            self._desc = bool(desc)
            return self

        def limit(self, n):
            self._limit = int(n)
            return self

        def execute(self):
            rows = [r for r in self._rows if r.get("signal") == self._signal]
            if self._desc:
                rows = sorted(
                    rows,
                    key=lambda r: float(r.get("expected_change_pct") or 0),
                    reverse=True,
                )
            else:
                rows = sorted(
                    rows,
                    key=lambda r: float(r.get("expected_change_pct") or 0),
                )
            return type("R", (), {"data": rows[: self._limit or 0]})()

    class _FakeClient:
        def __init__(self, rows):
            self._rows = rows

        def table(self, name):
            assert name == "market_quotes"
            return _FakeTable(self._rows)

    quote_rows = [
        {"card_id": "buy-1", "signal": "BUY", "expected_change_pct": 0.12},
        {"card_id": "buy-2", "signal": "BUY", "expected_change_pct": 0.08},
        {"card_id": "sell-1", "signal": "SELL", "expected_change_pct": -0.15},
    ]
    monkeypatch.setattr(dc, "get_supabase", lambda: _FakeClient(quote_rows))
    monkeypatch.setattr(dc, "hot_desk_sync_limit", lambda: 10)
    monkeypatch.setattr(
        "database_user.load_all_watchlists",
        lambda: pd.DataFrame([{"card_id": "wl-1"}, {"card_id": "buy-1"}]),
    )

    ids = dc.hot_desk_card_ids()
    assert "wl-1" in ids
    assert "buy-1" in ids
    assert "sell-1" in ids

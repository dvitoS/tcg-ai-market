"""distinct_history_card_ids must not scan the full 2M+ price_history table."""

from __future__ import annotations

import database_catalog as dc


def test_distinct_history_prefers_market_quotes(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def _fetch_all(table: str, cols: str = "*"):
        calls.append((table, cols))
        if table == "market_quotes":
            return [
                {"card_id": "a-1", "history_points": 90},
                {"card_id": "b-2", "history_points": 0},
                {"card_id": "c-3", "history_points": 12},
            ]
        raise AssertionError(f"unexpected fetch_all({table})")

    monkeypatch.setattr(dc, "fetch_all", _fetch_all)
    ids = dc.distinct_history_card_ids()
    assert ids == {"a-1", "c-3"}
    assert calls == [("market_quotes", "card_id,history_points")]


def test_distinct_history_fallback_chunks_cards(monkeypatch) -> None:
    class _FakeTable:
        def __init__(self):
            self._ids: list[str] = []

        def select(self, *_a, **_k):
            return self

        def in_(self, _col, ids):
            self._ids = list(ids)
            return self

        def limit(self, *_a, **_k):
            return self

        def execute(self):
            # Pretend only the first id in each chunk has history.
            data = [{"card_id": self._ids[0]}] if self._ids else []
            return type("R", (), {"data": data})()

    class _FakeClient:
        def table(self, name: str):
            assert name == "price_history"
            return _FakeTable()

    def _fetch_all(table: str, cols: str = "*"):
        if table == "market_quotes":
            return []
        if table == "cards":
            return [{"id": "x-1"}, {"id": "y-2"}, {"id": "z-3"}]
        raise AssertionError(table)

    monkeypatch.setattr(dc, "fetch_all", _fetch_all)
    monkeypatch.setattr(dc, "get_supabase", lambda: _FakeClient())
    monkeypatch.setattr(dc, "_chunked", lambda rows, size=80: [list(rows)])
    ids = dc.distinct_history_card_ids()
    assert ids == {"x-1"}

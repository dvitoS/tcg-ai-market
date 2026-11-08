"""price_history existence must not rely on exact COUNT(*) (57014)."""

from __future__ import annotations

import database_clients as clients


class _FakeQuery:
    def __init__(self, *, data=None, count=None, fail_modes=None):
        self._data = data
        self._count = count
        self._fail_modes = set(fail_modes or [])
        self._mode = None

    def select(self, *_args, **kwargs):
        self._mode = kwargs.get("count")
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self._mode in self._fail_modes:
            raise RuntimeError(f"count mode {self._mode} timed out")

        class _Resp:
            pass

        resp = _Resp()
        resp.data = self._data
        resp.count = self._count
        return resp


class _FakeTable:
    def __init__(self, query: _FakeQuery):
        self._query = query

    def select(self, *args, **kwargs):
        return self._query.select(*args, **kwargs)


class _FakeClient:
    def __init__(self, query: _FakeQuery):
        self._query = query

    def table(self, _name: str):
        return _FakeTable(self._query)


def test_table_has_rows_probes_without_count(monkeypatch):
    q = _FakeQuery(data=[{"card_id": "x"}], count=None)
    monkeypatch.setattr(clients, "get_supabase", lambda: _FakeClient(q))
    assert clients.table_has_rows("price_history") is True
    assert q._mode is None


def test_table_count_falls_back_when_exact_times_out(monkeypatch):
    # estimated fails, planned fails, exact fails → presence probe returns 1
    q = _FakeQuery(
        data=[{"card_id": "x"}],
        count=None,
        fail_modes={"estimated", "planned", "exact"},
    )
    monkeypatch.setattr(clients, "get_supabase", lambda: _FakeClient(q))
    assert clients.table_count("price_history") == 1


def test_table_count_uses_estimated_when_available(monkeypatch):
    q = _FakeQuery(data=[{"card_id": "x"}], count=2_032_626)
    monkeypatch.setattr(clients, "get_supabase", lambda: _FakeClient(q))
    assert clients.table_count("price_history") == 2_032_626

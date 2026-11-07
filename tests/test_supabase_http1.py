"""Regression: nightly history must survive Supabase HTTP/2 stream exhaustion."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest


def test_is_transient_connection_terminated():
    import database_clients as dc

    class RemoteProtocolError(Exception):
        pass

    exc = RemoteProtocolError(
        "<ConnectionTerminated error_code:0, last_stream_id:19999, additional_data:None>"
    )
    assert dc.is_transient_supabase_transport_error(exc) is True
    assert dc.is_transient_supabase_transport_error(ValueError("bad row")) is False


def test_call_with_supabase_reconnect_resets_then_succeeds(monkeypatch):
    import database_clients as dc

    class RemoteProtocolError(Exception):
        pass

    calls = {"n": 0, "resets": 0}

    def boom_then_ok():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RemoteProtocolError(
                "<ConnectionTerminated error_code:0, last_stream_id:19999>"
            )
        return "ok"

    monkeypatch.setattr(dc, "reset_supabase", lambda: calls.__setitem__("resets", calls["resets"] + 1))
    monkeypatch.setattr(dc.time, "sleep", lambda _s: None)

    assert dc.call_with_supabase_reconnect(boom_then_ok, retries=2) == "ok"
    assert calls["n"] == 2
    assert calls["resets"] == 1


def test_call_with_supabase_reconnect_gives_up(monkeypatch):
    import database_clients as dc

    class RemoteProtocolError(Exception):
        pass

    monkeypatch.setattr(dc, "reset_supabase", lambda: None)
    monkeypatch.setattr(dc.time, "sleep", lambda _s: None)

    with pytest.raises(RemoteProtocolError):
        dc.call_with_supabase_reconnect(
            lambda: (_ for _ in ()).throw(
                RemoteProtocolError("<ConnectionTerminated last_stream_id:19999>")
            ),
            retries=1,
        )


def test_http1_service_options_disables_http2():
    import database_clients as dc

    opts = dc._http1_service_options()
    assert opts is not None
    http = opts.httpx_client
    assert isinstance(http, httpx.Client)
    # httpcore ConnectionPool keeps the constructor flag on ``_http2``.
    assert http._transport._pool._http2 is False
    try:
        http.close()
    except Exception:
        pass


def test_get_supabase_prefers_http1_client(monkeypatch):
    import database_clients as dc

    captured: dict = {}

    def fake_create(url, key, options=None):
        captured["url"] = url
        captured["key"] = key
        captured["options"] = options
        return MagicMock(name="supabase-client")

    monkeypatch.setattr(dc, "_supabase_api", lambda: (object, fake_create))
    monkeypatch.setattr(
        dc,
        "_require_supabase_env",
        lambda: ("https://example.supabase.co", "service-key"),
    )
    dc.get_supabase.cache_clear()
    try:
        client = dc.get_supabase()
        assert client is not None
        opts = captured.get("options")
        assert opts is not None
        assert isinstance(getattr(opts, "httpx_client", None), httpx.Client)
    finally:
        dc.reset_supabase()


def test_replace_card_history_retries_after_protocol_error(monkeypatch):
    import database_catalog as catalog
    import database_clients as dc

    class RemoteProtocolError(Exception):
        pass

    delete_exec = MagicMock()
    insert_exec = MagicMock()
    state = {"fails": 1}

    def delete_execute():
        if state["fails"] > 0:
            state["fails"] -= 1
            raise RemoteProtocolError(
                "<ConnectionTerminated error_code:0, last_stream_id:19999>"
            )
        return delete_exec()

    table = MagicMock()
    table.delete.return_value.eq.return_value.execute.side_effect = delete_execute
    table.insert.return_value.execute.side_effect = lambda: insert_exec()

    client = MagicMock()
    client.table.return_value = table

    monkeypatch.setattr(catalog, "get_supabase", lambda: client)
    monkeypatch.setattr(dc, "get_supabase", lambda: client)
    monkeypatch.setattr(dc, "reset_supabase", lambda: None)
    monkeypatch.setattr(dc.time, "sleep", lambda _s: None)

    n = catalog.replace_card_history(
        "base1-1",
        [{"price": 1.25, "date": "2026-11-01"}],
    )
    assert n == 1
    assert insert_exec.called

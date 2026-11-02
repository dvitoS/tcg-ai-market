"""Auth session persistence: Cloud must not use local .data fallback."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def fake_st(monkeypatch):
    st = MagicMock()
    st.session_state = {}
    st.query_params = {}
    monkeypatch.setitem(__import__("sys").modules, "streamlit", st)
    return st


def test_cloud_write_raises_when_supabase_fails(monkeypatch, fake_st, tmp_path):
    import auth

    monkeypatch.setattr("config._is_streamlit_cloud", lambda: True)
    monkeypatch.setattr(auth, "_write_supabase_session", lambda *a, **k: False)
    monkeypatch.setattr(auth, "SESSIONS_DIR", tmp_path)

    with pytest.raises(RuntimeError, match="auth_sessions"):
        auth._write_server_session(
            "sid123",
            user={"id": "u1", "email": "a@b.c"},
            access="tok",
            refresh="ref",
        )
    assert list(tmp_path.glob("*.json")) == []


def test_local_write_falls_back_to_disk(monkeypatch, fake_st, tmp_path):
    import auth

    monkeypatch.setattr("config._is_streamlit_cloud", lambda: False)
    monkeypatch.setattr(auth, "_write_supabase_session", lambda *a, **k: False)
    monkeypatch.setattr(auth, "SESSIONS_DIR", tmp_path)

    auth._write_server_session(
        "sidLocal1",
        user={"id": "u1", "email": "a@b.c"},
        access="tok",
        refresh="ref",
    )
    assert (tmp_path / "sidLocal1.json").is_file()


def test_cloud_read_skips_local_disk(monkeypatch, fake_st, tmp_path):
    import auth
    import json

    monkeypatch.setattr("config._is_streamlit_cloud", lambda: True)
    monkeypatch.setattr(auth, "_read_supabase_session", lambda sid: None)
    monkeypatch.setattr(auth, "SESSIONS_DIR", tmp_path)
    (tmp_path / "sidCloud.json").write_text(
        json.dumps(
            {
                "user": {"id": "u1", "email": "a@b.c"},
                "access_token": "tok",
                "refresh_token": "ref",
                "updated_at": 9999999999,
            }
        ),
        encoding="utf-8",
    )
    assert auth._read_server_session("sidCloud") is None


def test_local_read_uses_disk_when_supabase_empty(monkeypatch, fake_st, tmp_path):
    import auth
    import json
    import time

    monkeypatch.setattr("config._is_streamlit_cloud", lambda: False)
    monkeypatch.setattr(auth, "_read_supabase_session", lambda sid: None)
    monkeypatch.setattr(auth, "SESSIONS_DIR", tmp_path)
    (tmp_path / "sidLocal2.json").write_text(
        json.dumps(
            {
                "user": {"id": "u1", "email": "a@b.c"},
                "access_token": "tok",
                "refresh_token": "ref",
                "updated_at": int(time.time()),
            }
        ),
        encoding="utf-8",
    )
    data = auth._read_server_session("sidLocal2")
    assert data is not None
    assert data["access_token"] == "tok"

"""Smoke tests for portfolio/watchlist client isolation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def fake_st(monkeypatch):
    st = MagicMock()
    st.session_state = {}
    monkeypatch.setitem(__import__("sys").modules, "streamlit", st)
    return st


def test_user_data_client_raises_without_jwt_when_auth_enabled(monkeypatch, fake_st):
    import database
    import database_clients

    monkeypatch.setattr(database_clients, "get_user_supabase", lambda: None)
    monkeypatch.setattr(database_clients, "get_supabase", lambda: MagicMock(name="service"))
    monkeypatch.setattr("config.auth_disabled", lambda: False)

    with pytest.raises(RuntimeError, match="JWT session"):
        database._user_data_client()


def test_user_data_client_allows_service_when_auth_disabled(monkeypatch, fake_st):
    import database
    import database_clients

    service = MagicMock(name="service")
    monkeypatch.setattr(database_clients, "get_user_supabase", lambda: None)
    monkeypatch.setattr(database_clients, "get_supabase", lambda: service)
    monkeypatch.setattr("config.auth_disabled", lambda: True)

    assert database._user_data_client() is service


def test_user_data_client_mode_anonymous_without_login(monkeypatch, fake_st):
    import auth
    import database

    monkeypatch.setattr(auth, "is_authenticated", lambda: False)
    assert database.user_data_client_mode() == "anonymous"


def test_user_data_client_mode_missing_anon(monkeypatch, fake_st):
    import auth
    import config
    import database
    import database_clients

    monkeypatch.setattr(auth, "is_authenticated", lambda: True)
    monkeypatch.setattr(auth, "has_jwt_tokens", lambda: True)
    monkeypatch.setattr(config, "auth_disabled", lambda: False)
    monkeypatch.setattr(database_clients, "_secret", lambda name, default="": "")
    monkeypatch.setattr(config, "_clean_secret_value", lambda v: "")
    monkeypatch.setattr(database_clients, "get_user_supabase", lambda: None)

    assert database.user_data_client_mode() == "missing_anon"


def test_jwt_role_claim_reads_anon():
    import base64
    import json

    import database_clients

    payload = base64.urlsafe_b64encode(
        json.dumps({"role": "anon", "ref": "x"}).encode()
    ).decode().rstrip("=")
    token = f"eyJhbGciOiJub25lIn0.{payload}.sig"
    assert database_clients.jwt_role_claim(token) == "anon"


def test_jwt_role_claim_detects_service_role():
    import base64
    import json

    import database_clients

    payload = base64.urlsafe_b64encode(
        json.dumps({"role": "service_role"}).encode()
    ).decode().rstrip("=")
    token = f"hdr.{payload}.sig"
    assert database_clients.jwt_role_claim(token) == "service_role"

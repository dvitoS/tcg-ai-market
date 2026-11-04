"""Soft Ink auth signup API (demo mode)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_signup_demo_returns_session() -> None:
    client = TestClient(app)
    res = client.post(
        "/api/auth/signup",
        json={"email": "new@example.com", "password": "secret1"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["needs_confirmation"] is False
    assert body["access_token"]
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["dev"] is True
    assert "signed in" in (body.get("message") or "").lower()


def test_signup_rejects_short_password() -> None:
    client = TestClient(app)
    res = client.post(
        "/api/auth/signup",
        json={"email": "new@example.com", "password": "123"},
    )
    assert res.status_code == 400
    assert "6" in res.json()["detail"]


def test_signup_rejects_empty_email() -> None:
    client = TestClient(app)
    res = client.post(
        "/api/auth/signup",
        json={"email": "   ", "password": "secret1"},
    )
    assert res.status_code == 400

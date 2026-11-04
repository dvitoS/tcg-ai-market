"""Soft Ink forgot / update password API (demo mode)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_forgot_password_demo_ok() -> None:
    client = TestClient(app)
    res = client.post(
        "/api/auth/forgot-password",
        json={"email": "you@example.com", "redirect_to": "http://localhost:3000/auth/reset"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "reset" in (body.get("message") or "").lower() or "email" in (
        body.get("message") or ""
    ).lower()


def test_forgot_password_rejects_bad_email() -> None:
    client = TestClient(app)
    res = client.post("/api/auth/forgot-password", json={"email": "not-an-email"})
    assert res.status_code == 400


def test_update_password_demo_ok() -> None:
    client = TestClient(app)
    res = client.post(
        "/api/auth/update-password",
        headers={"Authorization": "Bearer dev-local-token"},
        json={"password": "secret99", "refresh_token": "dev-local-token"},
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_update_password_rejects_short() -> None:
    client = TestClient(app)
    res = client.post(
        "/api/auth/update-password",
        headers={"Authorization": "Bearer dev-local-token"},
        json={"password": "123"},
    )
    assert res.status_code == 400

"""Operator allowlist for System status / data-health."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.deps import optional_user
from api.main import app
from services import ops as ops_mod
from services import prices as prices_mod


def test_is_ops_user_dev_and_email(monkeypatch) -> None:
    monkeypatch.setattr(ops_mod, "ops_allowlist_emails", lambda: {"owner@example.com"})
    monkeypatch.setattr(ops_mod, "ops_allowlist_user_ids", lambda: {"uid-1"})
    assert ops_mod.is_ops_user({"id": "x", "email": "owner@example.com", "dev": False})
    assert ops_mod.is_ops_user({"id": "uid-1", "email": "other@x.com", "dev": False})
    assert ops_mod.is_ops_user({"id": "d", "email": "anyone@x.com", "dev": True})
    assert not ops_mod.is_ops_user(
        {"id": "nope", "email": "random@example.com", "dev": False}
    )
    # Never trust a client-supplied ops flag alone.
    assert not ops_mod.is_ops_user(
        {"id": "nope", "email": "random@example.com", "dev": False, "ops": True}
    )


def test_data_health_forbidden_for_non_ops() -> None:
    prices_mod.reset_justtcg_observability()

    def _non_ops(_authorization=None):
        return {
            "id": "user-2",
            "email": "random@example.com",
            "dev": False,
            "ops": False,
        }

    app.dependency_overrides[optional_user] = _non_ops
    try:
        client = TestClient(app)
        assert client.get("/api/data-health").status_code == 403
        assert client.post("/api/data-health/reset").status_code == 403
    finally:
        app.dependency_overrides.pop(optional_user, None)


def test_data_health_ok_for_ops() -> None:
    prices_mod.reset_justtcg_observability()

    def _ops(_authorization=None):
        return {
            "id": "ops-1",
            "email": "vitoskender@gmail.com",
            "dev": False,
            "ops": True,
        }

    app.dependency_overrides[optional_user] = _ops
    try:
        client = TestClient(app)
        resp = client.get("/api/data-health")
        assert resp.status_code == 200
        assert "justtcg_configured" in resp.json()
    finally:
        app.dependency_overrides.pop(optional_user, None)

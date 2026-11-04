"""Public + authenticated billing status smoke tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.deps import optional_user
from api.main import app


def test_billing_status_shape(monkeypatch) -> None:
    monkeypatch.setenv("PRO_OPEN", "1")
    monkeypatch.setenv("PRO_CHECKOUT_URL", "https://creem.io/payment/prod_test")
    client = TestClient(app)
    res = client.get("/api/billing/status")
    assert res.status_code == 200
    body = res.json()
    assert body["pro_open"] is True
    assert body["checkout_url"] == "https://creem.io/payment/prod_test"


def test_billing_status_without_checkout(monkeypatch) -> None:
    monkeypatch.setenv("PRO_OPEN", "0")
    monkeypatch.delenv("PRO_CHECKOUT_URL", raising=False)
    import services.pro as pro

    monkeypatch.setattr(pro, "_clean", lambda name: "0" if name == "PRO_OPEN" else "")
    client = TestClient(app)
    res = client.get("/api/billing/status")
    assert res.status_code == 200
    body = res.json()
    assert body["pro_open"] is False
    assert body["checkout_url"] is None


def test_billing_me_paid_vs_free(monkeypatch) -> None:
    import services.pro as pro

    monkeypatch.setattr(
        pro,
        "_clean",
        lambda name: {
            "PRO_OPEN": "0",
            "PRO_CHECKOUT_URL": "https://creem.io/payment/prod_x",
            "CREEM_PORTAL_URL": "https://creem.io/portal",
        }.get(name, ""),
    )
    monkeypatch.setattr(pro, "auth_disabled", lambda: False)
    monkeypatch.setattr(
        pro,
        "_db_entitlement",
        lambda email, uid: email == "paid@x.com",
    )

    def _override_paid():
        return {"id": "u1", "email": "paid@x.com", "dev": False}

    def _override_free():
        return {"id": "u2", "email": "free@x.com", "dev": False}

    app.dependency_overrides[optional_user] = _override_paid
    try:
        client = TestClient(app)
        paid = client.get("/api/billing/me").json()
        assert paid["authenticated"] is True
        assert paid["is_pro"] is True
        assert paid["reason"] == "entitlement"
        assert paid["portal_url"] == "https://creem.io/portal"
        assert paid["email"] == "paid@x.com"
    finally:
        app.dependency_overrides.pop(optional_user, None)

    app.dependency_overrides[optional_user] = _override_free
    try:
        client = TestClient(app)
        free = client.get("/api/billing/me").json()
        assert free["authenticated"] is True
        assert free["is_pro"] is False
        assert free["reason"] == "locked"
        assert free["checkout_url"] == "https://creem.io/payment/prod_x"
    finally:
        app.dependency_overrides.pop(optional_user, None)

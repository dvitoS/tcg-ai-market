"""Public billing status smoke tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

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
    # services.pro reads via _clean → os.getenv; clear any leftover.
    import services.pro as pro

    monkeypatch.setattr(pro, "_clean", lambda name: "0" if name == "PRO_OPEN" else "")
    client = TestClient(app)
    res = client.get("/api/billing/status")
    assert res.status_code == 200
    body = res.json()
    assert body["pro_open"] is False
    assert body["checkout_url"] is None

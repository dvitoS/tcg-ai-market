"""Creem signature + Kestrel Pro grant handling (no live Creem/Supabase)."""

from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_verify_creem_signature_accepts_valid() -> None:
    from services.creem_webhooks import verify_creem_signature

    body = b'{"eventType":"checkout.completed"}'
    secret = "whsec_test"
    assert verify_creem_signature(body, _sign(body, secret), secret) is True
    assert verify_creem_signature(body, "deadbeef", secret) is False
    assert verify_creem_signature(body, _sign(body, secret), "") is False


def test_handle_subscription_trialing_grants_trialing(monkeypatch) -> None:
    import services.creem_webhooks as creem
    from services.trial_hygiene import reset_webhook_outcomes_for_tests

    reset_webhook_outcomes_for_tests()
    captured: dict = {}

    def fake_grant(**kwargs):
        captured.update(kwargs)
        return {"email": kwargs["email"], "status": kwargs["status"]}

    monkeypatch.setattr(
        "services.pro_entitlements.grant_pro_entitlement",
        fake_grant,
    )
    event = {
        "eventType": "subscription.trialing",
        "object": {
            "customer": {"id": "cust_t", "email": "Trial@Shop.com"},
            "subscription": {"id": "sub_t"},
            "product": {"id": "prod_1"},
        },
    }
    result = creem.handle_creem_event(event)
    assert result["ok"] is True
    assert result["status"] == "trialing"
    assert captured["status"] == "trialing"
    assert captured["email"] == "trial@shop.com"


def test_handle_checkout_completed_grants(monkeypatch) -> None:
    import services.creem_webhooks as creem

    captured: dict = {}

    def fake_grant(**kwargs):
        captured.update(kwargs)
        return {"email": kwargs["email"], "status": "active"}

    monkeypatch.setattr(
        "services.pro_entitlements.grant_pro_entitlement",
        fake_grant,
    )
    event = {
        "eventType": "checkout.completed",
        "object": {
            "object": "checkout",
            "id": "ch_1",
            "customer": {"id": "cust_1", "email": "Buyer@Shop.com"},
            "product": {"id": "prod_1", "name": "Kestrel Pro"},
            "order": {"id": "ord_1", "product": "prod_1"},
            "metadata": {"user_id": "uuid-buyer"},
        },
    }
    result = creem.handle_creem_event(event)
    assert result["ok"] is True
    assert result["action"] == "grant"
    assert result["status"] == "active"
    assert captured["status"] == "active"
    assert captured["email"] == "buyer@shop.com"
    assert captured["user_id"] == "uuid-buyer"
    assert captured["creem_product_id"] == "prod_1"
    assert captured["creem_checkout_id"] == "ch_1"


def test_handle_subscription_canceled_revokes(monkeypatch) -> None:
    import services.creem_webhooks as creem

    calls: list[dict] = []

    def fake_status(**kwargs):
        calls.append(kwargs)
        return 1

    monkeypatch.setattr(
        "services.pro_entitlements.set_entitlement_status_by_subscription",
        fake_status,
    )
    event = {
        "eventType": "subscription.canceled",
        "object": {
            "subscription": {"id": "sub_9"},
            "customer": {"email": "a@b.com"},
        },
    }
    result = creem.handle_creem_event(event)
    assert result["ok"] is True
    assert result["action"] == "revoke"
    assert calls == [{"subscription_id": "sub_9", "status": "canceled"}]


def test_webhook_route_rejects_bad_signature(monkeypatch) -> None:
    monkeypatch.setenv("CREEM_WEBHOOK_SECRET", "whsec_route")
    from api.main import app

    client = TestClient(app)
    body = {"eventType": "checkout.completed", "object": {}}
    raw = json.dumps(body).encode("utf-8")
    res = client.post(
        "/api/webhooks/creem",
        content=raw,
        headers={"content-type": "application/json", "creem-signature": "nope"},
    )
    assert res.status_code == 401


def test_webhook_route_accepts_valid_signature(monkeypatch) -> None:
    secret = "whsec_route_ok"
    monkeypatch.setenv("CREEM_WEBHOOK_SECRET", secret)

    def fake_handle(event):
        return {"ok": True, "action": "ignored", "event_type": event.get("eventType")}

    monkeypatch.setattr("api.routers.webhooks.handle_creem_event", fake_handle)
    from api.main import app

    client = TestClient(app)
    body = {"eventType": "ping", "object": {}}
    raw = json.dumps(body).encode("utf-8")
    res = client.post(
        "/api/webhooks/creem",
        content=raw,
        headers={
            "content-type": "application/json",
            "creem-signature": _sign(raw, secret),
        },
    )
    assert res.status_code == 200
    assert res.json()["action"] == "ignored"


def test_webhook_route_returns_500_when_grant_fails(monkeypatch) -> None:
    secret = "whsec_grant_fail"
    monkeypatch.setenv("CREEM_WEBHOOK_SECRET", secret)

    def fake_handle(_event):
        return {"ok": False, "action": "grant", "reason": "db_error", "event_type": "checkout.completed"}

    monkeypatch.setattr("api.routers.webhooks.handle_creem_event", fake_handle)
    from api.main import app

    client = TestClient(app)
    body = {"eventType": "checkout.completed", "id": "evt_1", "object": {}}
    raw = json.dumps(body).encode("utf-8")
    res = client.post(
        "/api/webhooks/creem",
        content=raw,
        headers={
            "content-type": "application/json",
            "creem-signature": _sign(raw, secret),
        },
    )
    assert res.status_code == 500



def test_is_pro_user_honors_db_entitlement(monkeypatch) -> None:
    import services.pro as pro

    monkeypatch.setattr(pro, "_clean", lambda name: "0" if name == "PRO_OPEN" else "vip@x.com")
    monkeypatch.setattr(pro, "auth_disabled", lambda: False)
    monkeypatch.setattr(
        pro,
        "_db_entitlement",
        lambda email, uid: email == "paid@shop.com",
    )
    assert pro.is_pro_user({"email": "paid@shop.com", "id": "u1"}) is True
    assert pro.is_pro_user({"email": "other@shop.com", "id": "u2"}) is False


def test_deploy_docs_mention_creem_webhook() -> None:
    from pathlib import Path

    docs = (Path(__file__).resolve().parents[1] / "docs" / "DEPLOY.md").read_text(
        encoding="utf-8"
    )
    assert "/api/webhooks/creem" in docs
    assert "PRO_CHECKOUT_URL" in docs
    assert "supabase_pro_entitlements.sql" in docs

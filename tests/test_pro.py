"""Soft Pro entitlement allowlist + Creem enforcement."""

from __future__ import annotations


def test_open_beta_default(monkeypatch):
    import services.pro as pro

    monkeypatch.setattr(pro, "_clean", lambda name: "")
    monkeypatch.setattr(pro, "auth_disabled", lambda: False)
    assert pro.pro_open_beta() is True
    assert pro.is_pro_user({"email": "a@b.com", "id": "u1"}) is True


def test_allowlist_when_pro_open_off(monkeypatch):
    import services.pro as pro

    def clean(name: str) -> str:
        return {
            "PRO_OPEN": "0",
            "PRO_EMAILS": "vip@shop.com, Other@Shop.com",
            "PRO_USER_IDS": "uuid-aaa",
        }.get(name, "")

    monkeypatch.setattr(pro, "_clean", clean)
    monkeypatch.setattr(pro, "auth_disabled", lambda: False)
    monkeypatch.setattr(pro, "_db_entitlement", lambda *_a, **_k: False)
    assert pro.is_pro_user({"email": "vip@shop.com", "id": "x"}) is True
    assert pro.is_pro_user({"email": "other@shop.com", "id": "x"}) is True
    assert pro.is_pro_user({"email": "nope@x.com", "id": "uuid-aaa"}) is True
    assert pro.is_pro_user({"email": "nope@x.com", "id": "other"}) is False


def test_auth_disabled_always_pro(monkeypatch):
    import services.pro as pro

    monkeypatch.setattr(pro, "_clean", lambda name: "0" if name == "PRO_OPEN" else "a@b.com")
    monkeypatch.setattr(pro, "auth_disabled", lambda: True)
    assert pro.is_pro_user({"email": "stranger@x.com", "id": "z"}) is True


def test_locked_without_allowlist_stays_open_until_creem(monkeypatch):
    """Before Creem is wired, PRO_OPEN=0 must not lock the whole product."""
    import services.pro as pro

    monkeypatch.setattr(
        pro, "_clean", lambda name: "0" if name == "PRO_OPEN" else ""
    )
    monkeypatch.setattr(pro, "auth_disabled", lambda: False)
    monkeypatch.setattr(pro, "_db_entitlement", lambda *_a, **_k: False)
    monkeypatch.setattr(pro, "creem_enforcement_ready", lambda: False)
    assert pro.is_pro_user({"email": "anyone@x.com", "id": "z"}) is True


def test_creem_wired_locks_unpaid_without_allowlist(monkeypatch):
    import services.pro as pro

    monkeypatch.setattr(
        pro,
        "_clean",
        lambda name: {
            "PRO_OPEN": "0",
            "PRO_CHECKOUT_URL": "https://www.creem.io/payment/prod_x",
        }.get(name, ""),
    )
    monkeypatch.setattr(pro, "auth_disabled", lambda: False)
    monkeypatch.setattr(pro, "_db_entitlement", lambda *_a, **_k: False)
    assert pro.creem_enforcement_ready() is True
    assert pro.is_pro_user({"email": "free@x.com", "id": "z"}) is False
    assert pro.pro_gate_reason({"email": "free@x.com", "id": "z"}) == "locked"


def test_creem_entitlement_unlocks_when_gated(monkeypatch):
    import services.pro as pro

    monkeypatch.setattr(
        pro,
        "_clean",
        lambda name: {
            "PRO_OPEN": "0",
            "PRO_CHECKOUT_URL": "https://www.creem.io/payment/prod_x",
        }.get(name, ""),
    )
    monkeypatch.setattr(pro, "auth_disabled", lambda: False)
    monkeypatch.setattr(
        pro,
        "_db_entitlement",
        lambda email, uid: email == "paid@x.com",
    )
    assert pro.is_pro_user({"email": "paid@x.com", "id": "u1"}) is True
    assert pro.pro_gate_reason({"email": "paid@x.com", "id": "u1"}) == "entitlement"
    assert pro.is_pro_user({"email": "free@x.com", "id": "u2"}) is False


def test_pro_checkout_url(monkeypatch):
    import services.pro as pro

    monkeypatch.setattr(pro, "_clean", lambda name: "")
    assert pro.pro_checkout_url() is None
    monkeypatch.setattr(
        pro,
        "_clean",
        lambda name: "https://buy.stripe.com/test" if name == "PRO_CHECKOUT_URL" else "",
    )
    assert pro.pro_checkout_url() == "https://buy.stripe.com/test"


def test_billing_snapshot_authenticated(monkeypatch):
    import services.pro as pro

    monkeypatch.setattr(
        pro,
        "_clean",
        lambda name: {
            "PRO_OPEN": "0",
            "PRO_CHECKOUT_URL": "https://creem.io/pay",
            "CREEM_PORTAL_URL": "https://creem.io/portal",
        }.get(name, ""),
    )
    monkeypatch.setattr(pro, "auth_disabled", lambda: False)
    monkeypatch.setattr(pro, "_db_entitlement", lambda email, uid: email == "paid@x.com")

    paid = pro.billing_snapshot({"email": "paid@x.com", "id": "u1"})
    assert paid["is_pro"] is True
    assert paid["authenticated"] is True
    assert paid["checkout_url"] == "https://creem.io/pay"
    assert paid["portal_url"] == "https://creem.io/portal"
    assert paid["reason"] == "entitlement"

    free = pro.billing_snapshot({"email": "free@x.com", "id": "u2"})
    assert free["is_pro"] is False
    assert free["reason"] == "locked"

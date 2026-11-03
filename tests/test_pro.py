"""Soft Pro entitlement allowlist."""

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
    assert pro.is_pro_user({"email": "vip@shop.com", "id": "x"}) is True
    assert pro.is_pro_user({"email": "other@shop.com", "id": "x"}) is True
    assert pro.is_pro_user({"email": "nope@x.com", "id": "uuid-aaa"}) is True
    assert pro.is_pro_user({"email": "nope@x.com", "id": "other"}) is False


def test_auth_disabled_always_pro(monkeypatch):
    import services.pro as pro

    monkeypatch.setattr(pro, "_clean", lambda name: "0" if name == "PRO_OPEN" else "a@b.com")
    monkeypatch.setattr(pro, "auth_disabled", lambda: True)
    assert pro.is_pro_user({"email": "stranger@x.com", "id": "z"}) is True


def test_locked_without_allowlist_stays_open(monkeypatch):
    import services.pro as pro

    monkeypatch.setattr(
        pro, "_clean", lambda name: "0" if name == "PRO_OPEN" else ""
    )
    monkeypatch.setattr(pro, "auth_disabled", lambda: False)
    assert pro.is_pro_user({"email": "anyone@x.com", "id": "z"}) is True


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

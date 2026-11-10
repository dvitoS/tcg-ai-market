"""eBay comps endpoint smoke tests (mocked — no live eBay)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_ebay_comps_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.ebay_listings.ebay.ebay_configured",
        lambda: False,
    )
    client = TestClient(app)
    res = client.get("/api/cards/sv1-1/ebay")
    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is False
    assert body["listings"] == []
    assert body["sold"] == []


def test_ebay_comps_with_mocked_listings(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.ebay_listings.ebay.ebay_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.ebay_listings.ebay.ebay_sold_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "services.ebay_listings.epn_configured",
        lambda: False,
    )
    monkeypatch.setattr(
        "services.ebay_listings.fetch_ebay_listings",
        lambda **kwargs: (
            [
                {
                    "item_id": "1",
                    "title": "Pikachu",
                    "price": 12.5,
                    "currency": "USD",
                    "condition": "Used",
                    "url": "https://www.ebay.com/itm/1",
                    "image": "",
                    "seller": "shop",
                }
            ],
            None,
        ),
    )
    client = TestClient(app)
    res = client.get("/api/cards/base1-58/ebay")
    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is True
    assert len(body["listings"]) == 1
    assert body["listings"][0]["price"] == 12.5
    # Sold proxy disabled — active Browse shown once only.
    assert body["sold"] == []
    assert body["sold_fallback_active"] is False
    assert body["active_fallback"] == []
    assert body["sold_hint"] == "ebay_sold_disabled"


def test_fetch_ebay_sold_comps_no_active_proxy(monkeypatch) -> None:
    """Insights miss must not clone active Browse into sold."""
    from services import ebay_listings as svc

    monkeypatch.setattr(svc.ebay, "ebay_sold_enabled", lambda: True)
    monkeypatch.setattr(svc.ebay, "ebay_configured", lambda: True)
    monkeypatch.setattr(
        svc.ebay,
        "sold_comps_for_card",
        lambda **kwargs: ([], "insights_unavailable"),
    )
    called = {"active": 0}

    def _boom_active(**_kwargs):
        called["active"] += 1
        return (
            [{"item_id": "x", "price": 9.0, "is_sold": False}],
            None,
        )

    monkeypatch.setattr(svc, "fetch_ebay_listings", _boom_active)
    rows, hint, stats = svc.fetch_ebay_sold_comps(
        card_id="sv1-1", name="Bulbasaur", set_name="SV"
    )
    assert rows == []
    assert hint == "insights_unavailable"
    assert float(stats.get("n") or 0) == 0.0
    assert called["active"] == 0

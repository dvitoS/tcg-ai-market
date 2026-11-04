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
    monkeypatch.setattr(
        "services.ebay_listings.fetch_ebay_sold_comps",
        lambda **kwargs: (
            [],
            "insights_unavailable",
            {"min": None, "median": None, "max": None, "n": 0.0, "is_sold": 0.0},
        ),
    )
    client = TestClient(app)
    res = client.get("/api/cards/base1-58/ebay")
    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is True
    assert len(body["listings"]) == 1
    assert body["listings"][0]["price"] == 12.5
    assert body["sold_fallback_active"] is False

"""Sealed product quote + ensure (demo seed)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from api.sealed_service import ensure_sealed_card, quote_sealed_products


def test_sealed_quote_demo_seed() -> None:
    client = TestClient(app)
    res = client.get("/api/sealed/quote", params={"q": "etb"})
    assert res.status_code == 200
    body = res.json()
    assert body["source"] in {"demo", "justtcg", "empty"}
    assert "items" in body
    if body["source"] == "demo":
        assert len(body["items"]) >= 1
        assert body["items"][0]["card_id"].startswith("sealed:")
        assert body["items"][0]["kind"] == "sealed"


def test_sealed_quote_showcase_without_query() -> None:
    client = TestClient(app)
    res = client.get("/api/sealed/quote")
    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "demo"
    assert len(body["items"]) >= 1
    assert body["items"][0]["card_id"].startswith("sealed:")


def test_ensure_sealed_demo() -> None:
    payload = quote_sealed_products(q="etb")
    assert payload["items"]
    hit = payload["items"][0]
    ensured = ensure_sealed_card(hit)
    assert ensured["ensured"] is True
    assert ensured["card_id"].startswith("sealed:")


def test_sealed_ensure_route() -> None:
    client = TestClient(app)
    res = client.post(
        "/api/sealed/ensure",
        json={
            "card_id": "sealed:demo-test",
            "name": "Demo ETB",
            "tcgplayer_id": "demo-test",
            "spot_usd": 40.0,
            "source": "demo",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["card_id"] == "sealed:demo-test"
    assert body["ensured"] is True

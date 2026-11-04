"""Multi-source card price history endpoint (mocked JustTCG — no live key)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app


def setup_function() -> None:
    clear_board_cache()


def test_card_price_sources_without_justtcg_key(monkeypatch) -> None:
    monkeypatch.setattr("api.price_sources_service.justtcg_api_key", lambda: "")
    client = TestClient(app)
    listing = client.get("/api/catalog", params={"limit": 1})
    assert listing.status_code == 200
    items = listing.json()["items"]
    if not items:
        return
    card_id = items[0]["id"]
    res = client.get(f"/api/cards/{card_id}/sources")
    assert res.status_code == 200
    body = res.json()
    assert body["card_id"] == card_id
    assert body["justtcg_configured"] is False
    assert isinstance(body["tcgplayer"], list)
    assert body["justtcg"] == []
    assert body["psa10"] == []
    assert body["justtcg_fallback"] is False
    assert "psa10_stats" in body
    assert body["psa10_stats"]["has_history_series"] is False


def test_card_price_sources_with_mocked_justtcg(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.price_sources_service.justtcg_api_key",
        lambda: "test-key",
    )
    monkeypatch.setattr(
        "justtcg_client.nm_history_for_card",
        lambda **kwargs: (
            [
                {"date": "2024-01-01", "price": 10.0},
                {"date": "2024-01-02", "price": 11.5},
            ],
            "tcp-123",
        ),
    )
    monkeypatch.setattr(
        "justtcg_client.psa10_history_for_card",
        lambda **kwargs: (
            [
                {"date": "2024-01-01", "price": 40.0},
                {"date": "2024-01-03", "price": 42.0},
            ],
            "tcp-123",
            {
                "has_history_series": True,
                "period_key": "30d",
                "sales_count": 12,
            },
        ),
    )
    client = TestClient(app)
    listing = client.get("/api/catalog", params={"limit": 1})
    assert listing.status_code == 200
    items = listing.json()["items"]
    if not items:
        return
    card_id = items[0]["id"]
    res = client.get(f"/api/cards/{card_id}/sources", params={"limit": 60})
    assert res.status_code == 200
    body = res.json()
    assert body["justtcg_configured"] is True
    assert body["tcgplayer_id"] == "tcp-123"
    assert len(body["justtcg"]) == 2
    assert body["justtcg"][0]["price"] == 10.0
    assert len(body["psa10"]) == 2
    assert body["psa10"][1]["price"] == 42.0
    assert body["psa10_stats"]["has_history_series"] is True
    assert body["psa10_stats"]["sales_count"] == 12
    assert body["justtcg_fallback"] is False
    assert body["justtcg_error"] is None
    assert body["psa10_error"] is None


def test_card_price_sources_justtcg_fallback_to_market(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.price_sources_service.justtcg_api_key",
        lambda: "test-key",
    )
    monkeypatch.setattr(
        "justtcg_client.nm_history_for_card",
        lambda **kwargs: ([], None),
    )
    monkeypatch.setattr(
        "justtcg_client.psa10_history_for_card",
        lambda **kwargs: ([], None, {"has_history_series": False, "sales_count": 0}),
    )
    monkeypatch.setattr(
        "api.price_sources_service.load_card_history",
        lambda card_id, limit=180: [
            {"date": "2024-02-01", "price": 3.25},
            {"date": "2024-02-02", "price": 3.4},
        ],
    )
    client = TestClient(app)
    res = client.get("/api/cards/demo-card/sources")
    assert res.status_code == 200
    body = res.json()
    assert body["justtcg_fallback"] is True
    assert len(body["justtcg"]) == 2
    assert body["justtcg"][0]["price"] == 3.25

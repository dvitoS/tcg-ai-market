"""Multi-source card price history endpoint (mocked JustTCG — no live key)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app
from api.price_sources_service import clear_price_sources_cache
from justtcg_client import JustTCGRateLimitError


def setup_function() -> None:
    clear_board_cache()
    clear_price_sources_cache()


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


def test_card_price_sources_caches_live_justtcg(monkeypatch) -> None:
    """Second Soft Ink detail view must not re-call JustTCG within the TTL."""
    calls = {"nm": 0, "psa": 0}

    def _nm(**kwargs):
        calls["nm"] += 1
        return ([{"date": "2024-01-01", "price": 9.0}], "tcp-1")

    def _psa(**kwargs):
        calls["psa"] += 1
        return ([], "tcp-1", {"has_history_series": False, "sales_count": 0})

    monkeypatch.setattr("api.price_sources_service.justtcg_api_key", lambda: "test-key")
    monkeypatch.setattr("justtcg_client.nm_history_for_card", _nm)
    monkeypatch.setattr("justtcg_client.psa10_history_for_card", _psa)
    monkeypatch.setattr(
        "api.price_sources_service.load_card_history",
        lambda card_id, limit=180: [{"date": "2024-01-01", "price": 8.0}],
    )

    client = TestClient(app)
    first = client.get("/api/cards/cache-card/sources")
    second = client.get("/api/cards/cache-card/sources")
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["cache"] == "miss"
    assert second.json()["cache"] == "hit"
    assert calls == {"nm": 1, "psa": 1}
    assert second.json()["justtcg"][0]["price"] == 9.0


def test_card_price_sources_uses_fresh_db_nm_without_live_call(monkeypatch) -> None:
    """Fresh nightly price_history should skip live JustTCG NM (quota)."""
    from datetime import date, timedelta

    calls = {"nm": 0, "psa": 0}
    today = date.today()
    market = [
        {"date": (today - timedelta(days=i)).isoformat(), "price": 10.0 + i}
        for i in range(14, -1, -1)
    ]

    def _nm(**kwargs):
        calls["nm"] += 1
        return ([{"date": today.isoformat(), "price": 99.0}], "tcp-db")

    def _psa(**kwargs):
        calls["psa"] += 1
        return (
            [{"date": today.isoformat(), "price": 50.0}],
            "tcp-db",
            {"has_history_series": True, "period_key": "30d", "sales_count": 3},
        )

    monkeypatch.setattr("api.price_sources_service.justtcg_api_key", lambda: "test-key")
    monkeypatch.setattr("justtcg_client.nm_history_for_card", _nm)
    monkeypatch.setattr("justtcg_client.psa10_history_for_card", _psa)
    monkeypatch.setattr(
        "api.price_sources_service.load_card_history",
        lambda card_id, limit=180: market,
    )

    client = TestClient(app)
    res = client.get("/api/cards/fresh-db-card/sources")
    assert res.status_code == 200
    body = res.json()
    assert calls["nm"] == 0
    assert calls["psa"] == 1
    assert body["justtcg_from_db"] is True
    assert body["justtcg_fallback"] is False
    assert len(body["justtcg"]) == 15
    assert body["justtcg"][-1]["price"] == market[-1]["price"]
    assert len(body["psa10"]) == 1


def test_card_price_sources_skips_psa10_after_nm_rate_limit(monkeypatch) -> None:
    calls = {"psa": 0}

    def _nm(**kwargs):
        raise JustTCGRateLimitError(response=None)

    def _psa(**kwargs):
        calls["psa"] += 1
        return ([], None, {})

    monkeypatch.setattr("api.price_sources_service.justtcg_api_key", lambda: "test-key")
    monkeypatch.setattr("justtcg_client.nm_history_for_card", _nm)
    monkeypatch.setattr("justtcg_client.psa10_history_for_card", _psa)
    monkeypatch.setattr(
        "api.price_sources_service.load_card_history",
        lambda card_id, limit=180: [{"date": "2024-01-01", "price": 1.0}],
    )

    client = TestClient(app)
    res = client.get("/api/cards/rl-card/sources")
    assert res.status_code == 200
    body = res.json()
    assert calls["psa"] == 0
    assert "rate limited" in (body["justtcg_error"] or "").lower()
    assert body["justtcg_fallback"] is True
    assert body["cache"] == "miss"
    # Rate-limited responses must not populate the TTL cache.
    again = client.get("/api/cards/rl-card/sources")
    assert again.json()["cache"] == "miss"

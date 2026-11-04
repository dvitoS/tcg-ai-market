"""Soft Ink watchlist alerts API."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app


def setup_function() -> None:
    clear_board_cache()


def test_watchlist_alerts_demo_ok() -> None:
    client = TestClient(app)
    res = client.get("/api/watchlist/alerts", params={"threshold_pct": 5, "sure_only": True})
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    assert body["threshold_pct"] == 5.0
    assert isinstance(body["sure_only"], bool)
    assert isinstance(body["sure_only_allowed"], bool)
    assert isinstance(body["watch_count"], int)
    assert body["source"] in {"supabase", "demo", "empty"}
    for item in body["items"]:
        assert item["card_id"]
        assert item["body"]
        assert item["reason"] in {"ai", "price", "both"}


def test_watchlist_alerts_respects_dismissed() -> None:
    client = TestClient(app)
    base = client.get("/api/watchlist/alerts", params={"threshold_pct": 1, "sure_only": False})
    assert base.status_code == 200
    items = base.json()["items"]
    if not items:
        return
    card_id = items[0]["card_id"]
    filtered = client.get(
        "/api/watchlist/alerts",
        params={"threshold_pct": 1, "sure_only": False, "dismissed": card_id},
    )
    assert filtered.status_code == 200
    assert all(row["card_id"] != card_id for row in filtered.json()["items"])


def test_watchlist_alerts_forces_sure_off_when_not_pro() -> None:
    with patch("api.alerts_service.is_pro_user", return_value=False):
        client = TestClient(app)
        res = client.get("/api/watchlist/alerts", params={"sure_only": True})
    assert res.status_code == 200
    body = res.json()
    assert body["sure_only_allowed"] is False
    assert body["sure_only"] is False

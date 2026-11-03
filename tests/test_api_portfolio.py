"""Portfolio / watchlist API smoke tests (demo mode — no Supabase)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app


def setup_function() -> None:
    clear_board_cache()


def test_portfolio_and_watchlist_demo_session() -> None:
    client = TestClient(app)
    portfolio = client.get("/api/portfolio")
    assert portfolio.status_code == 200
    body = portfolio.json()
    assert "items" in body
    assert "summary" in body
    assert body["demo"] is True
    assert body["summary"]["lots"] == len(
        [i for i in body["items"] if str(i.get("status") or "open") != "sold"]
    )

    watch = client.get("/api/watchlist")
    assert watch.status_code == 200
    wbody = watch.json()
    assert "items" in wbody
    assert wbody["demo"] is True


def test_watchlist_add_and_remove_roundtrip() -> None:
    client = TestClient(app)
    catalog = client.get("/api/catalog", params={"limit": 1})
    assert catalog.status_code == 200
    items = catalog.json()["items"]
    if not items:
        return
    card_id = items[0]["id"]

    added = client.post("/api/watchlist", json={"card_id": card_id})
    assert added.status_code == 201
    assert added.json()["card_id"] == card_id

    status = client.get(f"/api/watchlist/{card_id}/status")
    assert status.status_code == 200
    assert status.json()["watched"] is True

    removed = client.delete(f"/api/watchlist/{card_id}")
    assert removed.status_code == 200
    assert removed.json()["ok"] is True

"""FastAPI catalog smoke tests (demo seed — no Supabase required)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app


def setup_function() -> None:
    clear_board_cache()


def test_health_ok() -> None:
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["source"] in {"supabase", "demo", "empty"}
    assert isinstance(body.get("creem_webhook_secret"), bool)
    assert isinstance(body.get("pro_checkout_url"), bool)
    assert isinstance(body.get("pro_open"), bool)
    assert "git_sha" in body


def test_health_reports_render_git_sha(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123deadbeef")
    client = TestClient(app)
    body = client.get("/api/health").json()
    assert body["git_sha"] == "abc123deadbeef"


def test_catalog_returns_items_from_demo_or_live() -> None:
    client = TestClient(app)
    res = client.get("/api/catalog", params={"limit": 8})
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    assert "meta" in body
    assert body["limit"] == 8
    if body["meta"]["source"] != "empty":
        assert body["total"] > 0
        assert len(body["items"]) > 0
        card = body["items"][0]
        assert card["id"]
        assert card["name"]
        assert card["image_url"]


def test_card_detail_and_history_roundtrip() -> None:
    client = TestClient(app)
    listing = client.get("/api/catalog", params={"limit": 1})
    assert listing.status_code == 200
    items = listing.json()["items"]
    if not items:
        return
    card_id = items[0]["id"]
    detail = client.get(f"/api/cards/{card_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["card"]["id"] == card_id
    assert "history" in body
    assert "points" in body["history"]
    history = client.get(f"/api/cards/{card_id}/history")
    assert history.status_code == 200
    hist = history.json()
    assert hist["card_id"] == card_id
    assert "stats" in hist
    if hist["points"]:
        assert hist["stats"]["points"] == len(hist["points"])
        assert hist["stats"]["last_price"] is not None


def test_signals_board_shape() -> None:
    client = TestClient(app)
    res = client.get("/api/signals", params={"limit": 5})
    assert res.status_code == 200
    body = res.json()
    assert set(body) >= {"buys", "sells", "holds", "source"}

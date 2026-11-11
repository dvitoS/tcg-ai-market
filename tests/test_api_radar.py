"""Deal Radar API — conformal mispricing desk (demo board)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app
from api.radar_service import build_radar
from services.spot_sanity import (
    SHARE_SAFE_MAX_UNDER_EDGE_PCT,
    SHARE_SAFE_MIN_UNDER_SPOT,
)


def setup_function() -> None:
    clear_board_cache()


def test_radar_status_allowed_in_demo() -> None:
    client = TestClient(app)
    res = client.get("/api/radar/status")
    assert res.status_code == 200
    body = res.json()
    assert body["allowed"] is True
    assert body["forecast_days"] == 7
    assert "edge_floor" in body


def test_radar_bootstrap_status_and_board() -> None:
    """Desk mount: Pro status + first board in one round-trip."""
    client = TestClient(app)
    res = client.get("/api/radar/bootstrap", params={"min_edge": 0, "limit": 12})
    assert res.status_code == 200
    body = res.json()
    assert body["status"]["allowed"] is True
    assert "edge_floor" in body["status"]
    board = body["board"]
    assert board is not None
    assert "underpriced" in board
    assert "overpriced" in board
    assert board["scoped"] >= 0


def test_radar_bootstrap_locked_skips_board() -> None:
    """Non-Pro bootstrap returns status only — no board build cost."""
    from unittest.mock import patch

    from api.deps import require_user

    def _free_user() -> dict:
        return {"id": "free-1", "email": "free@x.com", "dev": False}

    app.dependency_overrides[require_user] = _free_user
    try:
        with patch("api.routers.radar.demo_mode", return_value=False), patch(
            "api.routers.radar.is_pro_user", return_value=False
        ), patch("api.routers.radar.build_radar") as build:
            client = TestClient(app)
            res = client.get("/api/radar/bootstrap", params={"limit": 12})
        assert res.status_code == 200
        body = res.json()
        assert body["status"]["allowed"] is False
        assert body["board"] is None
        build.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_user, None)


def test_radar_preview_public_under_only() -> None:
    from services.spot_sanity import RADAR_MAX_UNDER_EDGE_PCT, RADAR_MIN_UNDER_SPOT

    client = TestClient(app)
    res = client.get("/api/radar/preview", params={"limit": 5})
    assert res.status_code == 200
    body = res.json()
    assert "underpriced" in body
    assert "overpriced" not in body
    assert "relaxed" in body
    assert len(body["underpriced"]) <= 5
    edge_cap = (
        RADAR_MAX_UNDER_EDGE_PCT
        if body.get("relaxed")
        else SHARE_SAFE_MAX_UNDER_EDGE_PCT
    )
    spot_floor = (
        RADAR_MIN_UNDER_SPOT if body.get("relaxed") else SHARE_SAFE_MIN_UNDER_SPOT
    )
    for row in body["underpriced"]:
        assert row["side"] == "UNDER"
        assert float(row["edge_pct"]) > 0
        assert float(row["edge_pct"]) <= edge_cap
        spot = row.get("spot") if row.get("spot") is not None else row.get("price")
        assert float(spot) >= spot_floor
        if body.get("relaxed"):
            continue
        rarity = str(row.get("rarity") or "").lower()
        set_name = str(row.get("set_name") or "").lower()
        assert "promo" not in rarity
        assert "promo" not in set_name
        assert "black star" not in set_name


def test_radar_preview_deal_of_day_limit_one() -> None:
    client = TestClient(app)
    res = client.get("/api/radar/preview", params={"limit": 1})
    assert res.status_code == 200
    body = res.json()
    assert len(body["underpriced"]) <= 1
    if body["underpriced"]:
        top = body["underpriced"][0]
        assert top["side"] == "UNDER"
        assert top.get("image_url") is not None or top.get("name")
        assert float(top["edge_pct"]) > 0


def test_radar_preview_falls_back_when_share_safe_empty(monkeypatch) -> None:
    from api.routers import radar as radar_router

    calls: list[bool] = []

    def _fake_build(*, min_edge=0, limit=5, share_safe=True, **_k):
        calls.append(bool(share_safe))
        if share_safe:
            return {
                "forecast_days": 7,
                "under_total": 0,
                "underpriced": [],
                "source": "supabase",
            }
        return {
            "forecast_days": 7,
            "under_total": 1,
            "underpriced": [
                {
                    "id": "sv1-1",
                    "name": "Sprigatito",
                    "side": "UNDER",
                    "edge_pct": 12.0,
                    "spot": 4.0,
                    "price": 4.0,
                    "image_url": "https://example.com/x.png",
                }
            ],
            "source": "supabase",
        }

    monkeypatch.setattr(radar_router, "build_radar", _fake_build)
    client = TestClient(app)
    res = client.get("/api/radar/preview", params={"limit": 5})
    assert res.status_code == 200
    body = res.json()
    assert calls == [True, False]
    assert body["relaxed"] is True
    assert len(body["underpriced"]) == 1
    assert body["underpriced"][0]["id"] == "sv1-1"


def test_radar_board_returns_sides() -> None:
    client = TestClient(app)
    res = client.get("/api/radar", params={"min_edge": 0, "limit": 12})
    assert res.status_code == 200
    body = res.json()
    assert "underpriced" in body
    assert "overpriced" in body
    assert body["scoped"] >= 0
    assert body["sure_scoped"] >= 0
    if body["source"] != "empty":
        assert body["scoped"] > 0
        for row in body["underpriced"]:
            assert row["side"] == "UNDER"
            assert row["edge_pct"] is not None
            assert float(row["edge_pct"]) > 0
        for row in body["overpriced"]:
            assert row["side"] == "OVER"
            assert row["edge_pct"] is not None
            assert float(row["edge_pct"]) < 0


def test_build_radar_ranks_under_by_edge_desc() -> None:
    payload = build_radar(min_edge=0, limit=50)
    under = payload["underpriced"]
    if len(under) >= 2:
        edges = [float(r["edge_pct"]) for r in under]
        assert edges == sorted(edges, reverse=True)

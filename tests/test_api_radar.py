"""Deal Radar API — conformal mispricing desk (demo board)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app
from api.radar_service import build_radar


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


def test_radar_preview_public_under_only() -> None:
    client = TestClient(app)
    res = client.get("/api/radar/preview", params={"limit": 5})
    assert res.status_code == 200
    body = res.json()
    assert "underpriced" in body
    assert "overpriced" not in body
    assert len(body["underpriced"]) <= 5
    for row in body["underpriced"]:
        assert row["side"] == "UNDER"
        assert float(row["edge_pct"]) > 0


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

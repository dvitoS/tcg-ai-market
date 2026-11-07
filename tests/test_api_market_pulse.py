"""Public /api/market/pulse shape — Soft Ink landing desk."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app


def setup_function() -> None:
    clear_board_cache()


def test_market_pulse_shape() -> None:
    client = TestClient(app)
    res = client.get("/api/market/pulse", params={"movers": 5})
    assert res.status_code == 200
    body = res.json()
    assert body["source"] in {"supabase", "demo", "empty"}
    assert isinstance(body["board_total"], int)
    assert isinstance(body["sure_under"], int)
    assert isinstance(body["sure_over"], int)
    assert isinstance(body["signals"], dict)
    assert isinstance(body["risers"], list)
    assert isinstance(body["fallers"], list)
    assert len(body["risers"]) <= 5
    assert len(body["fallers"]) <= 5
    for mover in body["risers"] + body["fallers"]:
        assert mover["id"]
        assert mover["name"]
        assert "price_change_7d_pct" in mover

"""Public /api/market/pulse shape — Soft Ink landing desk."""

from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app
from api.market_pulse_service import _movers
from services.spot_sanity import RADAR_MAX_ABS_7D_CHANGE_PCT


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
        chg = mover.get("price_change_7d_pct")
        if chg is not None:
            assert abs(float(chg)) <= float(RADAR_MAX_ABS_7D_CHANGE_PCT)


def test_movers_skip_poison_7d_jumps() -> None:
    frame = pd.DataFrame(
        [
            {
                "id": "ecard2-H32",
                "name": "Umbreon",
                "set_name": "Aquapolis",
                "price": 3850.0,
                "price_change_7d_pct": 29768.1,
                "signal": "HOLD",
            },
            {
                "id": "bw10-16",
                "name": "Blastoise",
                "set_name": "Plasma Storm",
                "price": 988.0,
                "price_change_7d_pct": 120.0,
                "signal": "HOLD",
            },
        ]
    )
    risers = _movers(frame, ascending=False, limit=5)
    ids = {row["id"] for row in risers}
    assert "ecard2-H32" not in ids
    assert "bw10-16" in ids

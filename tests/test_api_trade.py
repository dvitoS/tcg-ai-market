"""Trade Analyzer API + scoring (demo board)."""

from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache, load_board
from api.main import app
from api.trade_service import analyze_trade


def setup_function() -> None:
    clear_board_cache()


def test_trade_status_allowed_in_demo() -> None:
    client = TestClient(app)
    res = client.get("/api/trade/status")
    assert res.status_code == 200
    body = res.json()
    assert body["allowed"] is True
    assert body["fair_band_pct"] == 3.0


def test_analyze_trade_even_spots_fair() -> None:
    board = pd.DataFrame(
        [
            {
                "id": "a",
                "name": "A",
                "price": 100.0,
                "predicted_price": 110.0,
                "expected_change_pct": 10.0,
                "conformal_ok": True,
                "confidence_ok": True,
            },
            {
                "id": "b",
                "name": "B",
                "price": 100.0,
                "predicted_price": 105.0,
                "expected_change_pct": 5.0,
                "conformal_ok": True,
                "confidence_ok": True,
            },
        ]
    )
    out = analyze_trade(
        board,
        you=[{"card_id": "a", "quantity": 1}],
        them=[{"card_id": "b", "quantity": 1}],
    )
    assert out["spot_verdict"] == "FAIR"
    assert out["net_spot_usd"] == 0.0
    assert out["ai_verdict"] == "THEM_AHEAD"  # you give 110 fair, get 105
    assert out["verdict"] == "THEM_AHEAD"


def test_trade_score_demo_board() -> None:
    client = TestClient(app)
    board, source = load_board()
    if source == "empty" or board is None or board.empty:
        return
    card_id = str(board.iloc[0]["id"])
    res = client.post(
        "/api/trade/score",
        json={
            "you": [{"card_id": card_id, "quantity": 1}],
            "them": [{"card_id": card_id, "quantity": 1}],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["verdict"] in {"FAIR", "YOU_AHEAD", "THEM_AHEAD"}
    assert body["you"]["matched"] == 1
    assert body["them"]["matched"] == 1
    assert abs(body["net_spot_usd"]) < 1e-6

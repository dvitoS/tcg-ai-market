"""Trade Analyzer API + scoring (demo board)."""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache, load_board
from api.main import app
from api.trade_service import analyze_trade
from api.trade_share import decode_trade_share, encode_trade_share


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


def test_encode_decode_trade_share_roundtrip() -> None:
    token = encode_trade_share(
        you=[{"card_id": "a", "quantity": 2}],
        them=[{"card_id": "b", "quantity": 1}],
        fair_band_pct=3.0,
    )
    decoded = decode_trade_share(token)
    assert decoded["you"] == [
        {"card_id": "a", "quantity": 2, "condition": "NM", "printing": "Normal"}
    ]
    assert decoded["them"] == [
        {"card_id": "b", "quantity": 1, "condition": "NM", "printing": "Normal"}
    ]
    assert decoded["fair_band_pct"] == 3.0


def test_decode_trade_share_rejects_tamper() -> None:
    token = encode_trade_share(
        you=[{"card_id": "a", "quantity": 1}],
        them=[{"card_id": "b", "quantity": 1}],
    )
    body, sig = token.rsplit(".", 1)
    with pytest.raises(ValueError):
        decode_trade_share(f"{body}x.{sig}")


def test_trade_share_create_and_public_view() -> None:
    client = TestClient(app)
    board, source = load_board()
    if source == "empty" or board is None or board.empty:
        return
    card_id = str(board.iloc[0]["id"])
    created = client.post(
        "/api/trade/share",
        json={
            "you": [{"card_id": card_id, "quantity": 1}],
            "them": [{"card_id": card_id, "quantity": 1}],
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["id"]
    assert body["path"].startswith("/trade/s/")
    view = client.get(f"/api/trade/share/{body['id']}")
    assert view.status_code == 200
    scored = view.json()
    assert scored["verdict"] in {"FAIR", "YOU_AHEAD", "THEM_AHEAD"}
    assert scored["share_id"] == body["id"]
    assert scored["you"]["matched"] == 1


def test_trade_share_view_bad_token_404() -> None:
    client = TestClient(app)
    res = client.get("/api/trade/share/not-a-real-token")
    assert res.status_code == 404

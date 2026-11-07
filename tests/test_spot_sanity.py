"""Spot / Radar UNDER sanity guards."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from api.radar_service import build_radar
from services.spot_sanity import (
    RADAR_MAX_UNDER_EDGE_PCT,
    is_absurd_spot_jump,
    under_deal_allowed,
)
import sync_justtcg as sync


def test_absurd_spot_jump_ratio() -> None:
    assert is_absurd_spot_jump(68.15, 1.80) is True
    assert is_absurd_spot_jump(1.90, 1.80) is False
    assert is_absurd_spot_jump(0.20, 1.60) is True
    assert is_absurd_spot_jump(12.0, None) is False


def test_under_deal_rejects_extreme_edge_and_bulk() -> None:
    assert under_deal_allowed(spot=0.21, edge_pct=809.0) is False
    assert under_deal_allowed(spot=20.14, edge_pct=238.0) is False
    assert under_deal_allowed(spot=48.0, edge_pct=27.0) is True
    assert under_deal_allowed(spot=5.0, edge_pct=RADAR_MAX_UNDER_EDGE_PCT) is True
    assert under_deal_allowed(spot=5.0, edge_pct=RADAR_MAX_UNDER_EDGE_PCT + 0.1) is False


def test_under_deal_rejects_poisoned_common_spot() -> None:
    assert under_deal_allowed(spot=68.15, edge_pct=32.0, rarity="Common") is False
    assert under_deal_allowed(spot=68.15, edge_pct=32.0, rarity="Rare") is True
    assert under_deal_allowed(spot=20.14, edge_pct=40.0, rarity="Uncommon") is True
    assert under_deal_allowed(spot=40.0, edge_pct=40.0, rarity="Uncommon") is False


def test_under_deal_rejects_wild_7d_move() -> None:
    assert (
        under_deal_allowed(spot=25.0, edge_pct=20.0, price_change_7d_pct=250.0) is False
    )
    assert (
        under_deal_allowed(spot=25.0, edge_pct=20.0, price_change_7d_pct=12.0) is True
    )


def test_ingest_skips_absurd_jump_vs_prior() -> None:
    card = SimpleNamespace(
        id="sm12-27",
        market_price=1.8,
        tcgplayer_id="1",
    )
    row = {
        "variants": [
            {
                "condition": "Near Mint",
                "price": 68.15,
                "priceHistory": [
                    {"date": f"2026-10-{d:02d}", "price": 68.15} for d in range(1, 15)
                ],
            }
        ],
    }
    updates: list[float] = []
    with patch.object(sync, "update_card_market_price", lambda *_a, **_k: updates.append(1)), patch.object(
        sync, "replace_card_history", lambda *_a, **_k: 14
    ):
        status, written = sync._ingest_card_row(
            card, row, have_history=set(), matched_ids=set()
        )
    assert status == "skip_absurd"
    assert written == 0
    assert updates == []


def test_build_radar_filters_poisoned_under(monkeypatch) -> None:
    board = pd.DataFrame(
        [
            {
                "id": "poison-common",
                "name": "Litwick",
                "set_name": "Unified Minds",
                "rarity": "Common",
                "supertype": "Pokémon",
                "price": 68.15,
                "market_price": 68.15,
                "predicted_price": 90.0,
                "expected_change_pct": 32.0,
                "pred_lo_pct": 32.0,
                "pred_hi_pct": 40.0,
                "price_change_7d_pct": 0.0,
                "signal": "BUY",
                "confidence_ok": True,
                "conformal_ok": True,
                "confidence_level": "high",
                "history_points": 90,
                "image_url": None,
            },
            {
                "id": "extreme-edge",
                "name": "Cyclizar",
                "set_name": "Paldean Fates",
                "rarity": "Rare",
                "supertype": "Pokémon",
                "price": 0.21,
                "market_price": 0.21,
                "predicted_price": 1.9,
                "expected_change_pct": 800.0,
                "pred_lo_pct": 800.0,
                "pred_hi_pct": 820.0,
                "price_change_7d_pct": 0.0,
                "signal": "BUY",
                "confidence_ok": True,
                "conformal_ok": True,
                "confidence_level": "high",
                "history_points": 90,
                "image_url": None,
            },
            {
                "id": "ok-under",
                "name": "Sharpedo",
                "set_name": "XY Promos",
                "rarity": "Rare Ultra",
                "supertype": "Pokémon",
                "price": 48.0,
                "market_price": 48.0,
                "predicted_price": 60.0,
                "expected_change_pct": 25.0,
                "pred_lo_pct": 25.0,
                "pred_hi_pct": 30.0,
                "price_change_7d_pct": 2.0,
                "signal": "BUY",
                "confidence_ok": True,
                "conformal_ok": True,
                "confidence_level": "high",
                "history_points": 90,
                "image_url": None,
            },
        ]
    )

    monkeypatch.setattr(
        "api.radar_service.load_board", lambda: (board.copy(), "test")
    )
    monkeypatch.setattr(
        "api.radar_service.filter_board",
        lambda frame, **_k: frame.copy(),
    )

    payload = build_radar(min_edge=0, limit=10)
    ids = [r["id"] for r in payload["underpriced"]]
    assert ids == ["ok-under"]
    assert payload["under_total"] == 1
    assert float(payload["underpriced"][0]["edge_pct"]) == 25.0

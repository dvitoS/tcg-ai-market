"""Dealer desk CSV parse + fee-aware actions."""

from __future__ import annotations

import pandas as pd

from services.dealer_desk import (
    ACTION_BUY_MORE,
    ACTION_HOLD,
    ACTION_LIST,
    build_dealer_board,
    desk_action,
    net_proceeds,
    parse_inventory_csv,
)
from trading_signals import SIGNAL_BUY, SIGNAL_HOLD, SIGNAL_SELL


def test_parse_inventory_csv_aliases():
    raw = b"id,qty,cost\nsv3-1,3,12.5\n"
    frame = parse_inventory_csv(raw)
    assert list(frame["card_id"]) == ["sv3-1"]
    assert int(frame.loc[0, "quantity"]) == 3
    assert float(frame.loc[0, "unit_cost"]) == 12.5


def test_net_proceeds_applies_fee_and_ship():
    assert net_proceeds(100.0, fee_pct=10.0, ship_usd=5.0) == 85.0


def test_desk_action_respects_conformal():
    assert (
        desk_action(
            signal=SIGNAL_BUY,
            expected_pct=10.0,
            conformal_ok=False,
            net_edge_pct=10.0,
        )
        == ACTION_HOLD
    )
    assert (
        desk_action(
            signal=SIGNAL_BUY,
            expected_pct=10.0,
            conformal_ok=True,
            net_edge_pct=10.0,
        )
        == ACTION_BUY_MORE
    )
    assert (
        desk_action(
            signal=SIGNAL_SELL,
            expected_pct=-10.0,
            conformal_ok=True,
            net_edge_pct=-10.0,
        )
        == ACTION_LIST
    )


def test_build_dealer_board_ranks_list_first():
    inventory = pd.DataFrame(
        [
            {"card_id": "a", "name": "A", "quantity": 1, "unit_cost": 10.0},
            {"card_id": "b", "name": "B", "quantity": 1, "unit_cost": 10.0},
            {"card_id": "missing", "name": "Nope", "quantity": 1, "unit_cost": 1.0},
        ]
    )
    market = pd.DataFrame(
        [
            {
                "id": "a",
                "name": "A",
                "set_name": "S",
                "price": 20.0,
                "expected_change_pct": -12.0,
                "signal": SIGNAL_SELL,
                "confidence_ok": True,
                "conformal_ok": True,
                "pred_lo_pct": -20.0,
                "pred_hi_pct": -4.0,
            },
            {
                "id": "b",
                "name": "B",
                "set_name": "S",
                "price": 20.0,
                "expected_change_pct": 1.0,
                "signal": SIGNAL_HOLD,
                "confidence_ok": True,
                "conformal_ok": True,
                "pred_lo_pct": -2.0,
                "pred_hi_pct": 4.0,
            },
        ]
    )
    board = build_dealer_board(inventory, market, fee_pct=10.0, ship_usd=0.0)
    assert board.attrs["unmatched"] == 1
    matched = board.loc[board["matched"]]
    assert matched.iloc[0]["card_id"] == "a"
    assert matched.iloc[0]["action"] == ACTION_LIST

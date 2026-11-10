"""Sure-desk Radar hit uses tip history, not arbitrary board head."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from api import trust_service as ts


def test_split_sure_sides_respects_min_edge() -> None:
    board = pd.DataFrame(
        [
            {
                "id": "weak",
                "signal": "BUY",
                "conformal_ok": True,
                "confidence_ok": True,
                "expected_change_pct": 5.0,
                "pred_lo_pct": 5.0,
                "pred_hi_pct": 12.0,
            },
            {
                "id": "strong",
                "signal": "BUY",
                "conformal_ok": True,
                "confidence_ok": True,
                "expected_change_pct": 15.0,
                "pred_lo_pct": 15.0,
                "pred_hi_pct": 22.0,
            },
        ]
    )
    sure = ts._sure_desk_frame(board)
    under, _over = ts._split_sure_sides(sure, sample_n=20, min_edge=12)
    assert [r["id"] for r in under] == ["strong"]


def test_split_sure_sides_prefers_buy_sell_signal() -> None:
    board = pd.DataFrame(
        [
            {
                "id": "u1",
                "signal": "BUY",
                "conformal_ok": True,
                "confidence_ok": True,
                "expected_change_pct": 12.0,
                "pred_lo_pct": 2.0,
                "pred_hi_pct": 20.0,
            },
            {
                "id": "o1",
                "signal": "SELL",
                "conformal_ok": True,
                "confidence_ok": True,
                "expected_change_pct": -10.0,
                "pred_lo_pct": -18.0,
                "pred_hi_pct": -3.0,
            },
            {
                "id": "hold",
                "signal": "HOLD",
                "conformal_ok": True,
                "confidence_ok": True,
                "expected_change_pct": 0.5,
                "pred_lo_pct": -2.0,
                "pred_hi_pct": 2.0,
            },
        ]
    )
    sure = ts._sure_desk_frame(board)
    under, over = ts._split_sure_sides(sure, sample_n=20)
    assert [r["id"] for r in under] == ["u1"]
    assert [r["id"] for r in over] == ["o1"]


def test_radar_backtest_scores_sure_tips(monkeypatch) -> None:
    today = date.today()
    board = pd.DataFrame(
        [
            {
                "id": "under-hit",
                "signal": "BUY",
                "conformal_ok": True,
                "confidence_ok": True,
                "expected_change_pct": 8.0,
                "pred_lo_pct": 1.0,
                "pred_hi_pct": 12.0,
            },
            {
                "id": "over-hit",
                "signal": "SELL",
                "conformal_ok": True,
                "confidence_ok": True,
                "expected_change_pct": -8.0,
                "pred_lo_pct": -12.0,
                "pred_hi_pct": -1.0,
            },
        ]
    )
    by_card = {
        "under-hit": pd.DataFrame(
            [
                {"date": pd.Timestamp(today - timedelta(days=7)), "price": 10.0},
                {"date": pd.Timestamp(today), "price": 12.0},
            ]
        ),
        "over-hit": pd.DataFrame(
            [
                {"date": pd.Timestamp(today - timedelta(days=7)), "price": 20.0},
                {"date": pd.Timestamp(today), "price": 16.0},
            ]
        ),
    }
    out = ts._radar_backtest(
        board, by_card, horizon_days=7, lookback_days=30, sample_n=20
    )
    assert out["n"] == 2
    assert out["hit_rate_pct"] == 100.0
    assert out["tighten_suggested"] is False


def test_build_trust_loads_history_for_sure_ids(monkeypatch) -> None:
    board = pd.DataFrame(
        [
            {
                "id": "noise-1",
                "signal": "HOLD",
                "conformal_ok": False,
                "confidence_ok": True,
                "expected_change_pct": 0.0,
                "pred_lo_pct": -1.0,
                "pred_hi_pct": 1.0,
            },
            {
                "id": "sure-buy",
                "signal": "BUY",
                "conformal_ok": True,
                "confidence_ok": True,
                "expected_change_pct": 9.0,
                "pred_lo_pct": 2.0,
                "pred_hi_pct": 15.0,
            },
        ]
    )
    loaded: list[str] = []

    monkeypatch.setattr(ts, "load_model_metrics", lambda *_a, **_k: {"metrics": {}})
    monkeypatch.setattr(ts, "load_board", lambda: (board, "supabase"))
    monkeypatch.setattr(ts, "demo_mode", lambda: False)

    def _hist(ids):
        loaded.extend(list(ids))
        return pd.DataFrame()

    monkeypatch.setattr(ts, "load_history_for_cards", _hist)
    ts.build_trust_report(horizon_days=7, sample_n=20)
    assert "sure-buy" in loaded

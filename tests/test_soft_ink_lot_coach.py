"""Soft Ink portfolio lot coach wiring (ADD / TRIM / HOLD + horizon)."""

from __future__ import annotations

import pandas as pd

from api.portfolio_service import portfolio_summary
from services.portfolio_outlook import ACTION_ADD, ACTION_HOLD, ACTION_TRIM, lot_action


def test_lot_action_thresholds_match_streamlit() -> None:
    assert lot_action(expected_pct=12.0, conformal_ok=True) == ACTION_ADD
    assert lot_action(expected_pct=-12.0, conformal_ok=True) == ACTION_TRIM
    assert lot_action(expected_pct=12.0, conformal_ok=False) == ACTION_HOLD
    assert lot_action(expected_pct=1.0, conformal_ok=True) == ACTION_HOLD


def test_portfolio_summary_exposes_outlook_horizon() -> None:
    lots = [
        {
            "status": "open",
            "market_value": 100.0,
            "invested": 80.0,
            "outlook_value": 110.0,
            "outlook_horizon_days": 30,
        },
        {
            "status": "sold",
            "market_value": 50.0,
            "invested": 40.0,
            "outlook_value": 55.0,
            "outlook_horizon_days": 30,
        },
    ]
    summary = portfolio_summary(lots)
    assert summary["lots"] == 1
    assert summary["outlook_horizon_days"] == 30
    assert abs(summary["outlook_pct"] - 10.0) < 1e-6


def test_attach_lot_outlook_fills_coach_fields(monkeypatch) -> None:
    from api import portfolio_service

    def _fake_history(_ids):
        return pd.DataFrame(columns=["card_id", "date", "price"])

    def _fake_enrich(view, history, *, fallback_model=None):
        out = view.copy()
        out["outlook_price"] = 12.0
        out["outlook_value"] = out["quantity"] * 12.0
        out["outlook_roi_pct"] = 15.0
        out["outlook_lo_pct"] = 5.0
        out["outlook_hi_pct"] = 25.0
        out["outlook_conformal_ok"] = True
        out["lot_action"] = ACTION_ADD
        out["is_top_ai"] = True
        out["week_price"] = 11.0
        out["week_value"] = out["quantity"] * 11.0
        out["week_roi_pct"] = 8.0
        return out, {"horizon_days": 30, "using_30d": True}

    monkeypatch.setattr(portfolio_service, "load_history_for_cards", _fake_history)
    monkeypatch.setattr(portfolio_service, "_board_encoding_by_id", lambda: {})
    monkeypatch.setattr(portfolio_service, "_fallback_board_model", lambda: None)

    import services.portfolio_outlook as outlook

    monkeypatch.setattr(outlook, "enrich_portfolio_outlook", _fake_enrich)

    lots = [
        {
            "card_id": "sv3-1",
            "quantity": 2,
            "current_price": 10.0,
            "market_price": 10.0,
            "status": "open",
        }
    ]
    enriched = portfolio_service._attach_lot_outlook(lots)
    assert len(enriched) == 1
    row = enriched[0]
    assert row["lot_action"] == "ADD"
    assert row["outlook_conformal_ok"] is True
    assert row["outlook_horizon_days"] == 30
    assert row["is_top_ai"] is True
    assert "rarity_encoded" not in row
    assert "week_price" not in row

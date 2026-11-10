"""Forward tip ledger — Sure Radar hits after the forecast horizon."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from services import tip_ledger as tl


def test_forward_return_pct() -> None:
    today = date.today()
    as_of = today - timedelta(days=10)
    frame = pd.DataFrame(
        [
            {"date": pd.Timestamp(as_of - timedelta(days=1)), "price": 10.0},
            {"date": pd.Timestamp(as_of), "price": 10.0},
            {"date": pd.Timestamp(as_of + timedelta(days=7)), "price": 12.0},
            {"date": pd.Timestamp(today), "price": 12.5},
        ]
    )
    got = tl.forward_return_pct(frame, as_of=as_of, horizon_days=7)
    assert got == 20.0


def test_score_forward_tips_hits(monkeypatch) -> None:
    today = date.today()
    as_of = today - timedelta(days=8)
    ledger = [
        {
            "card_id": "u1",
            "side": "UNDER",
            "edge_pct": 12.0,
            "pred_lo_pct": 2.0,
            "pred_hi_pct": 20.0,
            "as_of": as_of.isoformat(),
        },
        {
            "card_id": "o1",
            "side": "OVER",
            "edge_pct": -12.0,
            "pred_lo_pct": -20.0,
            "pred_hi_pct": -2.0,
            "as_of": as_of.isoformat(),
        },
        {
            "card_id": "pending",
            "side": "UNDER",
            "edge_pct": 15.0,
            "pred_lo_pct": 3.0,
            "pred_hi_pct": 18.0,
            "as_of": today.isoformat(),
        },
    ]
    monkeypatch.setattr(tl, "load_tip_ledger", lambda: ledger)
    by_card = {
        "u1": pd.DataFrame(
            [
                {"date": pd.Timestamp(as_of), "price": 10.0},
                {"date": pd.Timestamp(as_of + timedelta(days=7)), "price": 11.0},
            ]
        ),
        "o1": pd.DataFrame(
            [
                {"date": pd.Timestamp(as_of), "price": 20.0},
                {"date": pd.Timestamp(as_of + timedelta(days=7)), "price": 16.0},
            ]
        ),
    }
    out = tl.score_forward_tips(by_card, horizon_days=7, min_edge=0)
    assert out["method"] == "forward_tip_ledger"
    assert out["n"] == 2
    assert out["hit_rate_pct"] == 100.0
    assert out["pending_n"] == 1
    assert out["coverage_n"] == 2
    assert out["coverage_pct"] == 100.0


def test_build_trust_uses_forward_method(monkeypatch) -> None:
    from api import trust_service as ts

    monkeypatch.setattr(ts, "load_model_metrics", lambda *_a, **_k: {"metrics": {}})
    monkeypatch.setattr(
        ts, "load_board", lambda: (pd.DataFrame(), "empty")
    )
    monkeypatch.setattr(ts, "demo_mode", lambda: False)
    monkeypatch.setattr(
        "services.tip_ledger.load_tip_ledger",
        lambda: [],
    )
    monkeypatch.setattr(ts, "load_history_for_cards", lambda _ids: pd.DataFrame())
    payload = ts.build_trust_report(record_tips=False)
    assert payload["radar_backtest"]["method"] == "forward_tip_ledger"
    assert payload["radar_backtest"]["hit_rate_pct"] is None
    assert payload["conformal_coverage"]["method"] == "unavailable"
    assert payload["radar_backtest"].get("pending_n", 0) >= 0


def test_api_trust_accepts_forward_shape(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from api.catalog_service import clear_board_cache
    from api.main import app

    clear_board_cache()
    monkeypatch.setattr(
        "api.routers.trust.build_trust_report",
        lambda **kwargs: {
            "source": "empty",
            "trained_at": None,
            "artifact_id": "latest",
            "horizon_days": 7,
            "min_edge": 0,
            "calibration": {},
            "conformal_coverage": {
                "method": "unavailable",
                "target_pct": 80.0,
                "coverage_pct": None,
                "n": 0,
                "note": "waiting",
            },
            "radar_backtest": {
                "lookback_days": 7,
                "horizon_days": 7,
                "n": 0,
                "hit_rate_pct": None,
                "avg_move_pct": None,
                "under_n": 0,
                "over_n": 0,
                "min_edge": 0,
                "method": "forward_tip_ledger",
                "tighten_suggested": False,
                "pending_n": 12,
                "coverage_pct": None,
                "coverage_n": 0,
                "note": "collecting",
            },
        },
    )
    monkeypatch.setattr("api.routers.trust._pro_allowed", lambda _u: True)
    monkeypatch.setattr(
        "api.routers.trust.require_user",
        lambda: {"id": "u1", "email": "a@b.c", "dev": True},
    )

    # Bypass Depends(require_user) via dependency override.
    from api.deps import require_user

    app.dependency_overrides[require_user] = lambda: {
        "id": "u1",
        "email": "a@b.c",
        "dev": True,
    }
    try:
        client = TestClient(app)
        res = client.get("/api/trust")
        assert res.status_code == 200
        body = res.json()
        assert body["radar_backtest"]["method"] == "forward_tip_ledger"
        assert body["radar_backtest"]["pending_n"] == 12
        assert body["conformal_coverage"]["coverage_pct"] is None
    finally:
        app.dependency_overrides.pop(require_user, None)

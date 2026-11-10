"""Model trust API — calibration strip + coverage + radar-call hits."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app
from api.trust_service import build_trust_report


def setup_function() -> None:
    clear_board_cache()


def test_trust_status_allowed_in_demo() -> None:
    client = TestClient(app)
    res = client.get("/api/trust/status")
    assert res.status_code == 200
    body = res.json()
    assert body["allowed"] is True
    assert "checkout_url" in body


def test_trust_report_shape() -> None:
    client = TestClient(app)
    res = client.get(
        "/api/trust",
        params={"horizon_days": 7, "lookback_days": 30, "sample_n": 40},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["source"] in {"supabase", "demo", "empty"}
    assert body["horizon_days"] == 7
    assert "calibration" in body
    assert "conformal_coverage" in body
    assert "radar_backtest" in body
    cal = body["calibration"]
    assert "rmse" in cal
    assert "direction_accuracy_pct" in cal
    cov = body["conformal_coverage"]
    assert cov["target_pct"] > 0
    assert cov["method"] in {"unavailable", "forward_tip_ledger", "holdout"}
    bt = body["radar_backtest"]
    assert bt["n"] >= 0
    assert bt["method"] == "forward_tip_ledger"
    assert "hit_rate_pct" in bt
    assert "pending_n" in bt


def test_build_trust_report_tolerates_empty_metrics(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.trust_service.load_model_metrics",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "api.trust_service.load_board",
        lambda: (__import__("pandas").DataFrame(), "empty"),
    )
    monkeypatch.setattr(
        "services.tip_ledger.load_tip_ledger",
        lambda: [],
    )
    payload = build_trust_report(horizon_days=7, sample_n=20, record_tips=False)
    assert payload["calibration"]["rmse"] is None
    assert payload["conformal_coverage"]["target_pct"] == 80.0
    assert payload["radar_backtest"]["method"] == "forward_tip_ledger"
    assert payload["radar_backtest"]["hit_rate_pct"] is None
    assert payload["conformal_coverage"]["method"] == "unavailable"

"""Grading EV math (raw → PSA 10)."""

from __future__ import annotations

from services.grading_ev import compute_grading_ev, grading_sensitivity


def test_psa10_positive_edge() -> None:
    out = compute_grading_ev(
        raw_usd=40.0,
        psa10_usd=200.0,
        grade_fee_usd=25.0,
        ship_usd=15.0,
        sell_fee_pct=13.0,
    )
    assert out["ready"] is True
    assert out["all_in_usd"] == 80.0
    # 200 * 0.87 = 174; net = 174 - 80 = 94
    assert out["psa10"]["proceeds_usd"] == 174.0
    assert out["psa10"]["net_usd"] == 94.0
    assert abs(float(out["breakeven_psa10_usd"]) - (80.0 / 0.87)) < 1e-9


def test_missing_psa10_not_ready() -> None:
    out = compute_grading_ev(raw_usd=40.0, psa10_usd=None)
    assert out["ready"] is False
    assert out["psa10"]["net_usd"] is None


def test_psa9_heuristic_ratio() -> None:
    out = compute_grading_ev(
        raw_usd=50.0,
        psa10_usd=100.0,
        grade_fee_usd=0.0,
        ship_usd=0.0,
        sell_fee_pct=0.0,
        psa9_ratio=0.5,
    )
    assert out["psa9_usd"] == 50.0
    assert out["psa9_source"] == "ratio"
    assert out["psa9"]["net_usd"] == 0.0


def test_psa9_live_overrides_ratio() -> None:
    out = compute_grading_ev(
        raw_usd=50.0,
        psa10_usd=100.0,
        psa9_usd=70.0,
        grade_fee_usd=0.0,
        ship_usd=0.0,
        sell_fee_pct=0.0,
        psa9_ratio=0.5,
    )
    assert out["psa9_usd"] == 70.0
    assert out["psa9_source"] == "live"
    assert out["psa9"]["net_usd"] == 20.0


def test_grading_sensitivity_crosses_zero() -> None:
    points = grading_sensitivity(
        raw_usd=40.0,
        grade_fee_usd=25.0,
        ship_usd=15.0,
        sell_fee_pct=13.0,
        center_psa10_usd=100.0,
        steps=11,
        span=0.5,
    )
    assert len(points) == 11
    nets = [p["net_usd"] for p in points]
    assert min(nets) < 0 < max(nets)

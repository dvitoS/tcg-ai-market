"""AI fair band + drawdown callouts for portfolio performance."""

from __future__ import annotations

from api.portfolio_service import _ai_fair_band, _drawdown_callouts


def test_ai_fair_band_sums_outlook_and_optional_conformal() -> None:
    band = _ai_fair_band(
        [
            {
                "outlook_value": 110.0,
                "market_price": 100.0,
                "quantity": 1,
                "outlook_lo_pct": -5.0,
                "outlook_hi_pct": 10.0,
            },
            {
                "outlook_value": 55.0,
                "market_price": 50.0,
                "quantity": 1,
                "outlook_lo_pct": -5.0,
                "outlook_hi_pct": 10.0,
            },
        ]
    )
    assert band["ai_fair_value"] == 165.0
    # 100*(1-0.05) + 50*(1-0.05) = 142.5 ; hi uses +10% → 165
    assert abs(float(band["ai_lo"]) - 142.5) < 1e-6
    assert abs(float(band["ai_hi"]) - 165.0) < 1e-6


def test_drawdown_callouts_pick_deepest_trough() -> None:
    points = [
        {"date": "2024-01-01", "market_value": 100.0},
        {"date": "2024-01-02", "market_value": 120.0},
        {"date": "2024-01-03", "market_value": 90.0},
        {"date": "2024-01-04", "market_value": 80.0},
        {"date": "2024-01-05", "market_value": 110.0},
    ]
    lots = [{"lot_action": "TRIM", "outlook_conformal_ok": True}]
    out = _drawdown_callouts(points, open_lots=lots, min_drawdown_pct=8.0, limit=2)
    assert out
    assert out[0]["trough_date"] == "2024-01-04"
    assert out[0]["peak_date"] == "2024-01-02"
    assert out[0]["trim_count"] == 1
    assert abs(float(out[0]["drawdown_pct"]) - (40.0 / 120.0 * 100.0)) < 0.1

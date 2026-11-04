"""Card AI explain service smoke tests."""

from __future__ import annotations

from datetime import date, timedelta

from api.explain_service import build_card_explain


def test_build_card_explain_short_series() -> None:
    points = [{"date": f"2024-01-{i:02d}", "price": 1.0 + i * 0.01} for i in range(1, 10)]
    out = build_card_explain(
        points=points,
        last_price=1.09,
        predicted_price=1.12,
        pred_lo_pct=-2.0,
        pred_hi_pct=4.0,
    )
    assert out["confidence_level"] == "low"
    assert out["confidence_ok"] is False
    assert out["rows"]  # still explains expected move / band from spot


def test_build_card_explain_with_lags() -> None:
    start = date(2024, 1, 1)
    points = [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "price": 10.0 + i * 0.08 + ((-1) ** i) * 0.03,
        }
        for i in range(40)
    ]
    out = build_card_explain(
        points=points,
        last_price=points[-1]["price"],
        predicted_price=points[-1]["price"] * 1.04,
        pred_lo_pct=-1.5,
        pred_hi_pct=6.0,
    )
    assert out["confidence_ok"] is True
    assert out["confidence_level"] in {"medium", "high"}
    labels = [row["label"] for row in out["rows"]]
    assert "7d return" in labels
    assert "Expected move" in labels
    assert "80% interval" in labels

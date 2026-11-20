"""Parity mirror of web/src/lib/deskNumbers.ts (T1.2)."""

from __future__ import annotations


def resolve_desk_numbers(
    *,
    price=None,
    spot=None,
    last_price=None,
    predicted_price=None,
    fair_price=None,
    side=None,
):
    def finite(n):
        if n is None:
            return None
        try:
            v = float(n)
        except (TypeError, ValueError):
            return None
        if v != v:
            return None
        return v

    asking = finite(last_price) or finite(spot) or finite(price)
    good = finite(fair_price) or finite(predicted_price)
    edge = None
    if asking is not None and asking > 0 and good is not None:
        edge = ((good - asking) / asking) * 100
    out_side = None
    hint = str(side or "").upper()
    if hint in {"UNDER", "OVER"}:
        out_side = hint
    elif edge is not None:
        if edge > 0.5:
            out_side = "UNDER"
        elif edge < -0.5:
            out_side = "OVER"
    return {"asking": asking, "good": good, "edge_gap_pct": edge, "side": out_side}


def test_gap_matches_detail_hero():
    out = resolve_desk_numbers(last_price=10.0, predicted_price=12.0)
    assert out["asking"] == 10.0
    assert out["good"] == 12.0
    assert abs(out["edge_gap_pct"] - 20.0) < 1e-9
    assert out["side"] == "UNDER"


def test_prefers_fair_over_predicted():
    out = resolve_desk_numbers(
        spot=8.0, fair_price=9.0, predicted_price=100.0, side="UNDER"
    )
    assert out["asking"] == 8.0
    assert out["good"] == 9.0
    assert abs(out["edge_gap_pct"] - 12.5) < 1e-9


def test_overpriced_gap():
    out = resolve_desk_numbers(spot=20.0, fair_price=15.0)
    assert out["side"] == "OVER"
    assert out["edge_gap_pct"] < 0

"""Raw → PSA 10 grading EV helpers (no live network)."""

from __future__ import annotations

from typing import Any

DEFAULT_GRADE_FEE_USD = 25.0
DEFAULT_SHIP_USD = 15.0
DEFAULT_SELL_FEE_PCT = 13.0
# Rough PSA 9 vs PSA 10 heuristic when only PSA 10 comps exist.
DEFAULT_PSA9_RATIO = 0.45

# Typical service fee+ship presets (USD). Sell fee stays marketplace-specific.
FEE_PRESETS: dict[str, dict[str, float]] = {
    "psa_value": {"grade_fee_usd": 19.0, "ship_usd": 15.0},
    "psa_regular": {"grade_fee_usd": 25.0, "ship_usd": 15.0},
    "psa_express": {"grade_fee_usd": 50.0, "ship_usd": 20.0},
    "cgc_standard": {"grade_fee_usd": 20.0, "ship_usd": 15.0},
}


def compute_grading_ev(
    *,
    raw_usd: float | None,
    psa10_usd: float | None,
    grade_fee_usd: float = DEFAULT_GRADE_FEE_USD,
    ship_usd: float = DEFAULT_SHIP_USD,
    sell_fee_pct: float = DEFAULT_SELL_FEE_PCT,
    psa9_ratio: float = DEFAULT_PSA9_RATIO,
    psa9_usd: float | None = None,
) -> dict[str, Any]:
    """Net EV if you buy raw, grade, and sell at PSA 10 (and PSA 9)."""
    fee = max(0.0, float(grade_fee_usd))
    ship = max(0.0, float(ship_usd))
    sell = max(0.0, min(100.0, float(sell_fee_pct)))
    ratio = max(0.0, min(1.0, float(psa9_ratio)))

    raw = float(raw_usd) if raw_usd is not None else None
    psa10 = float(psa10_usd) if psa10_usd is not None else None
    live_psa9 = float(psa9_usd) if psa9_usd is not None else None
    if raw is not None and raw < 0:
        raw = None
    if psa10 is not None and psa10 < 0:
        psa10 = None
    if live_psa9 is not None and live_psa9 < 0:
        live_psa9 = None

    all_in = (raw + fee + ship) if raw is not None else None
    net_mult = 1.0 - sell / 100.0

    def _side(exit_price: float | None) -> dict[str, float | None]:
        if exit_price is None or all_in is None or net_mult <= 0:
            return {
                "exit_usd": exit_price,
                "proceeds_usd": None,
                "net_usd": None,
                "roi_pct": None,
            }
        proceeds = float(exit_price) * net_mult
        net = proceeds - float(all_in)
        roi = (net / float(all_in)) * 100.0 if all_in > 0 else None
        return {
            "exit_usd": float(exit_price),
            "proceeds_usd": float(proceeds),
            "net_usd": float(net),
            "roi_pct": float(roi) if roi is not None else None,
        }

    if live_psa9 is not None:
        psa9 = live_psa9
        psa9_source = "live"
    else:
        psa9 = (psa10 * ratio) if psa10 is not None else None
        psa9_source = "ratio" if psa9 is not None else "none"

    breakeven = (float(all_in) / net_mult) if all_in is not None and net_mult > 0 else None

    return {
        "raw_usd": raw,
        "psa10_usd": psa10,
        "psa9_usd": float(psa9) if psa9 is not None else None,
        "psa9_source": psa9_source,
        "grade_fee_usd": fee,
        "ship_usd": ship,
        "sell_fee_pct": sell,
        "psa9_ratio": ratio,
        "all_in_usd": float(all_in) if all_in is not None else None,
        "breakeven_psa10_usd": float(breakeven) if breakeven is not None else None,
        "psa10": _side(psa10),
        "psa9": _side(psa9),
        "ready": raw is not None and psa10 is not None,
    }


def grading_sensitivity(
    *,
    raw_usd: float | None,
    grade_fee_usd: float = DEFAULT_GRADE_FEE_USD,
    ship_usd: float = DEFAULT_SHIP_USD,
    sell_fee_pct: float = DEFAULT_SELL_FEE_PCT,
    center_psa10_usd: float | None = None,
    steps: int = 21,
    span: float = 0.5,
) -> list[dict[str, float]]:
    """Net EV vs PSA 10 exit — sweep ±span around center (or breakeven)."""
    steps = max(3, min(int(steps or 21), 61))
    span = max(0.1, min(float(span or 0.5), 0.9))
    base = compute_grading_ev(
        raw_usd=raw_usd,
        psa10_usd=center_psa10_usd,
        grade_fee_usd=grade_fee_usd,
        ship_usd=ship_usd,
        sell_fee_pct=sell_fee_pct,
    )
    center = center_psa10_usd
    if center is None or center <= 0:
        center = base.get("breakeven_psa10_usd")
    if center is None or float(center) <= 0:
        return []

    center_f = float(center)
    lo = center_f * (1.0 - span)
    hi = center_f * (1.0 + span)
    if hi <= lo:
        return []

    out: list[dict[str, float]] = []
    for i in range(steps):
        t = i / (steps - 1)
        exit_px = lo + (hi - lo) * t
        side = compute_grading_ev(
            raw_usd=raw_usd,
            psa10_usd=exit_px,
            grade_fee_usd=grade_fee_usd,
            ship_usd=ship_usd,
            sell_fee_pct=sell_fee_pct,
        )["psa10"]
        net = side.get("net_usd")
        if net is None:
            continue
        out.append({"psa10_usd": round(exit_px, 4), "net_usd": round(float(net), 4)})
    return out

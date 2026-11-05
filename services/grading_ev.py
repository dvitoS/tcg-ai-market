"""Raw → PSA 10 grading EV helpers (no live network)."""

from __future__ import annotations

from typing import Any

DEFAULT_GRADE_FEE_USD = 25.0
DEFAULT_SHIP_USD = 15.0
DEFAULT_SELL_FEE_PCT = 13.0
# Rough PSA 9 vs PSA 10 heuristic when only PSA 10 comps exist.
DEFAULT_PSA9_RATIO = 0.45


def compute_grading_ev(
    *,
    raw_usd: float | None,
    psa10_usd: float | None,
    grade_fee_usd: float = DEFAULT_GRADE_FEE_USD,
    ship_usd: float = DEFAULT_SHIP_USD,
    sell_fee_pct: float = DEFAULT_SELL_FEE_PCT,
    psa9_ratio: float = DEFAULT_PSA9_RATIO,
) -> dict[str, Any]:
    """Net EV if you buy raw, grade, and sell at PSA 10 (and heuristic PSA 9)."""
    fee = max(0.0, float(grade_fee_usd))
    ship = max(0.0, float(ship_usd))
    sell = max(0.0, min(100.0, float(sell_fee_pct)))
    ratio = max(0.0, min(1.0, float(psa9_ratio)))

    raw = float(raw_usd) if raw_usd is not None else None
    psa10 = float(psa10_usd) if psa10_usd is not None else None
    if raw is not None and raw < 0:
        raw = None
    if psa10 is not None and psa10 < 0:
        psa10 = None

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

    psa9 = (psa10 * ratio) if psa10 is not None else None
    breakeven = (float(all_in) / net_mult) if all_in is not None and net_mult > 0 else None

    return {
        "raw_usd": raw,
        "psa10_usd": psa10,
        "psa9_usd": float(psa9) if psa9 is not None else None,
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

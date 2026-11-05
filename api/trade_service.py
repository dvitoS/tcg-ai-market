"""Two-sided trade analyzer vs Soft Ink market board AI."""

from __future__ import annotations

from typing import Any

import pandas as pd

from api.catalog_service import row_to_card

FAIR_SPOT_BAND_PCT = 3.0  # within ±3% spot = FAIR


def _match_card(board: pd.DataFrame, card_id: str) -> pd.Series | None:
    cid = str(card_id or "").strip()
    if not cid or board is None or board.empty:
        return None
    hits = board[board["id"].astype(str) == cid]
    if hits.empty and "card_id" in board.columns:
        hits = board[board["card_id"].astype(str) == cid]
    if hits.empty:
        return None
    return hits.iloc[0]


def _line(
    board: pd.DataFrame,
    *,
    card_id: str,
    quantity: int = 1,
    condition: str = "NM",
    printing: str = "Normal",
) -> dict[str, Any]:
    from services.lot_price_adjust import (
        adjust_nm_price,
        lot_price_factor,
        normalize_condition,
        normalize_printing,
    )

    qty = max(1, int(quantity or 1))
    cond = normalize_condition(condition)
    print_ = normalize_printing(printing)
    factor = lot_price_factor(condition=cond, printing=print_)
    row = _match_card(board, card_id)
    if row is None:
        return {
            "card_id": str(card_id),
            "quantity": qty,
            "condition": cond,
            "printing": print_,
            "price_factor": factor,
            "matched": False,
            "name": None,
            "set_name": None,
            "image_url": None,
            "spot": None,
            "fair_price": None,
            "expected_change_pct": None,
            "pred_lo_pct": None,
            "pred_hi_pct": None,
            "signal": None,
            "conformal_ok": False,
            "line_spot": None,
            "line_fair": None,
        }
    card = row_to_card(row)
    nm_spot = card.get("price")
    fair = card.get("predicted_price")
    if fair is None and nm_spot is not None and card.get("expected_change_pct") is not None:
        try:
            fair = float(nm_spot) * (1.0 + float(card["expected_change_pct"]) / 100.0)
        except (TypeError, ValueError):
            fair = None
    spot = adjust_nm_price(nm_spot, condition=cond, printing=print_)
    fair = adjust_nm_price(fair, condition=cond, printing=print_)
    lo = row.get("pred_lo_pct")
    hi = row.get("pred_hi_pct")
    try:
        lo_f = float(lo) if lo is not None and not (isinstance(lo, float) and pd.isna(lo)) else None
    except (TypeError, ValueError):
        lo_f = None
    try:
        hi_f = float(hi) if hi is not None and not (isinstance(hi, float) and pd.isna(hi)) else None
    except (TypeError, ValueError):
        hi_f = None
    line_spot = float(spot) * qty if spot is not None else None
    line_fair = float(fair) * qty if fair is not None else None
    return {
        "card_id": card["id"],
        "quantity": qty,
        "condition": cond,
        "printing": print_,
        "price_factor": factor,
        "matched": True,
        "name": card.get("name"),
        "set_name": card.get("set_name"),
        "image_url": card.get("image_url"),
        "spot": spot,
        "fair_price": fair,
        "expected_change_pct": card.get("expected_change_pct"),
        "pred_lo_pct": lo_f,
        "pred_hi_pct": hi_f,
        "signal": card.get("signal"),
        "conformal_ok": bool(card.get("conformal_ok")),
        "line_spot": line_spot,
        "line_fair": line_fair,
    }


def _side_totals(lines: list[dict[str, Any]]) -> dict[str, Any]:
    matched = [r for r in lines if r.get("matched")]
    spot = sum(float(r["line_spot"]) for r in matched if r.get("line_spot") is not None)
    fair = sum(float(r["line_fair"]) for r in matched if r.get("line_fair") is not None)
    return {
        "lines": lines,
        "matched": len(matched),
        "unmatched": len(lines) - len(matched),
        "spot_total": float(spot) if matched else 0.0,
        "fair_total": float(fair) if matched else 0.0,
        "cards": sum(int(r.get("quantity") or 1) for r in matched),
    }


def analyze_trade(
    board: pd.DataFrame,
    *,
    you: list[dict[str, Any]],
    them: list[dict[str, Any]],
    fair_band_pct: float = FAIR_SPOT_BAND_PCT,
) -> dict[str, Any]:
    """Score a trade from YOUR perspective: you give `you`, receive `them`."""
    you_lines = [
        _line(
            board,
            card_id=str(item.get("card_id") or ""),
            quantity=int(item.get("quantity") or 1),
            condition=str(item.get("condition") or "NM"),
            printing=str(item.get("printing") or "Normal"),
        )
        for item in you
        if str(item.get("card_id") or "").strip()
    ]
    them_lines = [
        _line(
            board,
            card_id=str(item.get("card_id") or ""),
            quantity=int(item.get("quantity") or 1),
            condition=str(item.get("condition") or "NM"),
            printing=str(item.get("printing") or "Normal"),
        )
        for item in them
        if str(item.get("card_id") or "").strip()
    ]
    you_side = _side_totals(you_lines)
    them_side = _side_totals(them_lines)

    # Positive net = you receive more value than you give.
    net_spot = float(them_side["spot_total"]) - float(you_side["spot_total"])
    net_fair = float(them_side["fair_total"]) - float(you_side["fair_total"])
    denom = max(float(you_side["spot_total"]), 1e-9)
    net_spot_pct = (net_spot / denom) * 100.0
    net_fair_pct = (net_fair / max(float(you_side["fair_total"]), 1e-9)) * 100.0

    band = abs(float(fair_band_pct))
    if abs(net_spot_pct) <= band:
        spot_verdict = "FAIR"
    elif net_spot_pct > 0:
        spot_verdict = "YOU_AHEAD"
    else:
        spot_verdict = "THEM_AHEAD"

    if abs(net_fair_pct) <= band:
        ai_verdict = "FAIR"
    elif net_fair_pct > 0:
        ai_verdict = "YOU_AHEAD"
    else:
        ai_verdict = "THEM_AHEAD"

    # Prefer AI when both sides have fair totals; else spot.
    has_ai = you_side["matched"] > 0 and them_side["matched"] > 0
    primary = ai_verdict if has_ai else spot_verdict

    return {
        "you": you_side,
        "them": them_side,
        "net_spot_usd": float(net_spot),
        "net_fair_usd": float(net_fair),
        "net_spot_pct": float(net_spot_pct),
        "net_fair_pct": float(net_fair_pct),
        "spot_verdict": spot_verdict,
        "ai_verdict": ai_verdict,
        "verdict": primary,
        "fair_band_pct": float(band),
    }

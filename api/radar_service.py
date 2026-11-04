"""Deal Radar — conformal mispricing desk from precomputed market_quotes."""

from __future__ import annotations

from typing import Any

import pandas as pd

from api.catalog_service import filter_board, load_board, row_to_card
from trading_signals import FORECAST_DAYS

# Conservative edge floor (%): lower conformal bound must clear this for UNDER deals.
RADAR_EDGE_FLOOR = 0.0


def radar_defaults() -> dict[str, Any]:
    return {
        "forecast_days": int(FORECAST_DAYS),
        "edge_floor": float(RADAR_EDGE_FLOOR),
    }


def _edge_under(row: pd.Series) -> float | None:
    """Conservative underprice edge: pred_lo_pct, else expected_change_pct."""
    lo = row.get("pred_lo_pct")
    if lo is not None and not (isinstance(lo, float) and pd.isna(lo)):
        try:
            return float(lo)
        except (TypeError, ValueError):
            pass
    exp = row.get("expected_change_pct")
    if exp is None or (isinstance(exp, float) and pd.isna(exp)):
        return None
    try:
        return float(exp)
    except (TypeError, ValueError):
        return None


def _edge_over(row: pd.Series) -> float | None:
    """Conservative overprice edge: pred_hi_pct, else expected_change_pct (negative = rich)."""
    hi = row.get("pred_hi_pct")
    if hi is not None and not (isinstance(hi, float) and pd.isna(hi)):
        try:
            return float(hi)
        except (TypeError, ValueError):
            pass
    exp = row.get("expected_change_pct")
    if exp is None or (isinstance(exp, float) and pd.isna(exp)):
        return None
    try:
        return float(exp)
    except (TypeError, ValueError):
        return None


def _fair_price(row: pd.Series, spot: float | None) -> float | None:
    predicted = row.get("predicted_price")
    if predicted is not None and not (isinstance(predicted, float) and pd.isna(predicted)):
        try:
            return float(predicted)
        except (TypeError, ValueError):
            pass
    if spot is None or spot <= 0:
        return None
    exp = row.get("expected_change_pct")
    if exp is None or (isinstance(exp, float) and pd.isna(exp)):
        return None
    try:
        return float(spot) * (1.0 + float(exp) / 100.0)
    except (TypeError, ValueError):
        return None


def build_radar(
    *,
    q: str | None = None,
    set_name: str | None = None,
    rarity: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_edge: float = RADAR_EDGE_FLOOR,
    limit: int = 24,
) -> dict[str, Any]:
    board, source = load_board()
    defaults = radar_defaults()
    empty = {
        **defaults,
        "source": source,
        "scoped": 0,
        "sure_scoped": 0,
        "min_edge": float(min_edge),
        "sets": [],
        "rarities": [],
        "underpriced": [],
        "overpriced": [],
        "under_total": 0,
        "over_total": 0,
    }
    if board is None or board.empty:
        return empty

    scoped = filter_board(
        board,
        q=q,
        set_name=set_name,
        min_price=min_price,
        max_price=max_price,
        mode="browse",
    )
    if rarity and rarity.strip() and rarity.strip().lower() not in {"all", "sve"}:
        if "rarity" in scoped.columns:
            scoped = scoped[
                scoped["rarity"].astype(str) == rarity.strip()
            ].reset_index(drop=True)

    if scoped is None or scoped.empty:
        return {**empty, "source": source, "min_edge": float(min_edge)}

    conf = scoped.get("confidence_ok")
    conf_ok = (
        conf.fillna(True).astype(bool)
        if conf is not None
        else pd.Series(True, index=scoped.index)
    )
    conformal = scoped.get("conformal_ok")
    conformal_ok = (
        conformal.fillna(True).astype(bool)
        if conformal is not None
        else pd.Series(True, index=scoped.index)
    )
    sure = scoped.loc[conf_ok & conformal_ok].copy()

    under_rows: list[dict[str, Any]] = []
    over_rows: list[dict[str, Any]] = []

    for _, row in sure.iterrows():
        card = row_to_card(row)
        spot = card.get("price")
        fair = _fair_price(row, spot if isinstance(spot, (int, float)) else None)
        lo = None
        hi = None
        raw_lo = row.get("pred_lo_pct")
        raw_hi = row.get("pred_hi_pct")
        try:
            if raw_lo is not None and not (isinstance(raw_lo, float) and pd.isna(raw_lo)):
                lo = float(raw_lo)
        except (TypeError, ValueError):
            lo = None
        try:
            if raw_hi is not None and not (isinstance(raw_hi, float) and pd.isna(raw_hi)):
                hi = float(raw_hi)
        except (TypeError, ValueError):
            hi = None

        edge_u = _edge_under(row)
        edge_o = _edge_over(row)
        base = {
            **card,
            "spot": spot,
            "fair_price": fair,
            "pred_lo_pct": lo,
            "pred_hi_pct": hi,
            "current_price": spot,
            "ai_target_price": fair,
        }
        floor = float(min_edge)
        under_ok = (
            edge_u is not None
            and (edge_u > 0 if floor == 0.0 else edge_u >= floor)
        )
        over_ok = (
            edge_o is not None
            and (edge_o < 0 if floor == 0.0 else edge_o <= -floor)
        )
        if under_ok:
            under_rows.append(
                {
                    **base,
                    "side": "UNDER",
                    "edge_pct": float(edge_u),
                    "expected_roi_pct": card.get("expected_change_pct"),
                }
            )
        if over_ok:
            over_rows.append(
                {
                    **base,
                    "side": "OVER",
                    "edge_pct": float(edge_o),
                    "expected_roi_pct": card.get("expected_change_pct"),
                }
            )

    under_rows.sort(key=lambda r: float(r["edge_pct"]), reverse=True)
    over_rows.sort(key=lambda r: float(r["edge_pct"]))

    rarities = sorted(
        {
            str(r)
            for r in scoped.get("rarity", pd.Series(dtype=str)).dropna().astype(str).tolist()
            if str(r).strip()
        }
    )
    sets = sorted(
        {
            str(s)
            for s in scoped.get("set_name", pd.Series(dtype=str)).dropna().astype(str).tolist()
            if str(s).strip()
        }
    )

    return {
        **defaults,
        "source": source,
        "scoped": int(len(scoped)),
        "sure_scoped": int(len(sure)),
        "min_edge": float(min_edge),
        "sets": sets,
        "rarities": rarities,
        "underpriced": under_rows[: int(limit)],
        "overpriced": over_rows[: int(limit)],
        "under_total": int(len(under_rows)),
        "over_total": int(len(over_rows)),
    }

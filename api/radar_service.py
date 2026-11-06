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


def _fair_price_from_row(row: pd.Series, spot: float | None) -> float | None:
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


def _rows_from_frame(frame: pd.DataFrame, *, side: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        card = row_to_card(row)
        spot = card.get("price")
        fair = _fair_price_from_row(row, spot if isinstance(spot, (int, float)) else None)
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
        edge = float(row["_edge"])
        out.append(
            {
                **card,
                "spot": spot,
                "fair_price": fair,
                "pred_lo_pct": lo,
                "pred_hi_pct": hi,
                "current_price": spot,
                "ai_target_price": fair,
                "side": side,
                "edge_pct": edge,
                "expected_roi_pct": card.get("expected_change_pct"),
            }
        )
    return out


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

    # Vectorized edge ranking — only materialize top-N card dicts.
    lo = pd.to_numeric(sure.get("pred_lo_pct"), errors="coerce")
    hi = pd.to_numeric(sure.get("pred_hi_pct"), errors="coerce")
    exp = pd.to_numeric(sure.get("expected_change_pct"), errors="coerce")
    edge_u = lo.where(lo.notna(), exp)
    edge_o = hi.where(hi.notna(), exp)
    floor = float(min_edge)
    if floor == 0.0:
        under_mask = edge_u.notna() & (edge_u > 0)
        over_mask = edge_o.notna() & (edge_o < 0)
    else:
        under_mask = edge_u.notna() & (edge_u >= floor)
        over_mask = edge_o.notna() & (edge_o <= -floor)

    under_frame = (
        sure.loc[under_mask]
        .assign(_edge=edge_u.loc[under_mask])
        .sort_values("_edge", ascending=False)
    )
    over_frame = (
        sure.loc[over_mask]
        .assign(_edge=edge_o.loc[over_mask])
        .sort_values("_edge", ascending=True)
    )

    under_rows = _rows_from_frame(under_frame.head(int(limit)), side="UNDER")
    over_rows = _rows_from_frame(over_frame.head(int(limit)), side="OVER")

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
        "underpriced": under_rows,
        "overpriced": over_rows,
        "under_total": int(under_mask.sum()),
        "over_total": int(over_mask.sum()),
    }

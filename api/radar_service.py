"""Deal Radar — conformal mispricing desk from precomputed market_quotes."""

from __future__ import annotations

from typing import Any

import pandas as pd

from api.catalog_service import filter_board, load_board, row_to_card
from services.spot_sanity import (
    RADAR_MAX_ABS_7D_CHANGE_PCT,
    RADAR_MAX_UNDER_EDGE_PCT,
    RADAR_MIN_UNDER_SPOT,
    SHARE_SAFE_MAX_UNDER_EDGE_PCT,
    SHARE_SAFE_MIN_UNDER_SPOT,
    is_bulk_common,
    share_safe_under_deal,
    under_deal_allowed,
)
from trading_signals import FORECAST_DAYS

# Conservative edge floor (%): lower conformal bound must clear this for UNDER deals.
RADAR_EDGE_FLOOR = 0.0


def radar_defaults() -> dict[str, Any]:
    return {
        "forecast_days": int(FORECAST_DAYS),
        "edge_floor": float(RADAR_EDGE_FLOOR),
        "max_under_edge_pct": float(RADAR_MAX_UNDER_EDGE_PCT),
        "min_under_spot": float(RADAR_MIN_UNDER_SPOT),
        "max_abs_7d_change_pct": float(RADAR_MAX_ABS_7D_CHANGE_PCT),
        "share_safe_max_under_edge_pct": float(SHARE_SAFE_MAX_UNDER_EDGE_PCT),
        "share_safe_min_under_spot": float(SHARE_SAFE_MIN_UNDER_SPOT),
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
    share_safe: bool = False,
) -> dict[str, Any]:
    board, source = load_board()
    defaults = radar_defaults()
    empty = {
        **defaults,
        "source": source,
        "scoped": 0,
        "sure_scoped": 0,
        "min_edge": float(min_edge),
        "share_safe": bool(share_safe),
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
        return {
            **empty,
            "source": source,
            "min_edge": float(min_edge),
            "share_safe": bool(share_safe),
        }

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

    # Trust gate: drop absurd edges, bulk UNDER noise, rarity/spot poison, 7d jumps.
    # Public preview/DOTD uses share_safe (stricter edge/spot + no promo lanes).
    spot = pd.to_numeric(sure.get("price"), errors="coerce")
    chg7 = pd.to_numeric(sure.get("price_change_7d_pct"), errors="coerce")
    rarities = (
        sure["rarity"] if "rarity" in sure.columns else pd.Series([None] * len(sure), index=sure.index)
    )
    set_names = (
        sure["set_name"]
        if "set_name" in sure.columns
        else pd.Series([None] * len(sure), index=sure.index)
    )
    quarantined = (
        sure["spot_quarantine"].fillna(False).astype(bool)
        if "spot_quarantine" in sure.columns
        else pd.Series(False, index=sure.index)
    )
    names = (
        sure["name"] if "name" in sure.columns else pd.Series([None] * len(sure), index=sure.index)
    )
    supertypes = (
        sure["supertype"]
        if "supertype" in sure.columns
        else pd.Series([None] * len(sure), index=sure.index)
    )
    if share_safe:
        trust_u = pd.Series(
            [
                share_safe_under_deal(
                    spot=s,
                    edge_pct=e,
                    rarity=r,
                    set_name=sn,
                    name=nm,
                    supertype=st,
                    price_change_7d_pct=c,
                    spot_quarantine=qflag,
                )
                for s, e, r, sn, nm, st, c, qflag in zip(
                    spot.tolist(),
                    edge_u.tolist(),
                    rarities.tolist(),
                    set_names.tolist(),
                    names.tolist(),
                    supertypes.tolist(),
                    chg7.tolist(),
                    quarantined.tolist(),
                    strict=False,
                )
            ],
            index=sure.index,
        )
    else:
        trust_u = pd.Series(
            [
                under_deal_allowed(
                    spot=s,
                    edge_pct=e,
                    rarity=r,
                    price_change_7d_pct=c,
                )
                and not bool(qflag)
                for s, e, r, c, qflag in zip(
                    spot.tolist(),
                    edge_u.tolist(),
                    rarities.tolist(),
                    chg7.tolist(),
                    quarantined.tolist(),
                    strict=False,
                )
            ],
            index=sure.index,
        )
    under_mask = under_mask & trust_u

    # OVER: same bulk floor / Common skip + quarantine as UNDER.
    spot_ok = spot.notna() & (spot >= float(RADAR_MIN_UNDER_SPOT))
    not_common = pd.Series(
        [not is_bulk_common(r) for r in rarities.tolist()],
        index=sure.index,
    )
    over_mask = over_mask & spot_ok & not_common & ~quarantined

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
        "share_safe": bool(share_safe),
        "sets": sets,
        "rarities": rarities,
        "underpriced": under_rows,
        "overpriced": over_rows,
        "under_total": int(under_mask.sum()),
        "over_total": int(over_mask.sum()),
    }


def _soft_under_fill(
    *,
    need: int,
    exclude: set[str],
    min_price: float,
) -> list[dict[str, Any]]:
    """Fill DOTD seats with ≥$min_price cards where asking < good price.

    Used when the sure UNDER desk is thin after the public $10 floor — still
    share-safe gated, but without requiring conformal sure.
    """
    if need <= 0:
        return []
    board, _source = load_board()
    if board is None or board.empty:
        return []
    scoped = filter_board(board, min_price=float(min_price), mode="browse")
    if scoped is None or scoped.empty:
        return []

    spot = pd.to_numeric(scoped.get("price"), errors="coerce")
    fair = pd.to_numeric(scoped.get("predicted_price"), errors="coerce")
    edge = ((fair - spot) / spot) * 100.0
    edge = edge.where(spot.notna() & (spot >= float(min_price)) & fair.notna() & (fair > 0))

    rarities = (
        scoped["rarity"] if "rarity" in scoped.columns else pd.Series([None] * len(scoped), index=scoped.index)
    )
    set_names = (
        scoped["set_name"]
        if "set_name" in scoped.columns
        else pd.Series([None] * len(scoped), index=scoped.index)
    )
    names = (
        scoped["name"] if "name" in scoped.columns else pd.Series([None] * len(scoped), index=scoped.index)
    )
    supertypes = (
        scoped["supertype"]
        if "supertype" in scoped.columns
        else pd.Series([None] * len(scoped), index=scoped.index)
    )
    chg7 = pd.to_numeric(scoped.get("price_change_7d_pct"), errors="coerce")
    quarantined = (
        scoped["spot_quarantine"].fillna(False).astype(bool)
        if "spot_quarantine" in scoped.columns
        else pd.Series(False, index=scoped.index)
    )
    ids = scoped["id"].astype(str) if "id" in scoped.columns else pd.Series([""] * len(scoped), index=scoped.index)

    ok = []
    for idx, cid, s, e, r, sn, nm, st, c, qflag in zip(
        scoped.index.tolist(),
        ids.tolist(),
        spot.tolist(),
        edge.tolist(),
        rarities.tolist(),
        set_names.tolist(),
        names.tolist(),
        supertypes.tolist(),
        chg7.tolist(),
        quarantined.tolist(),
        strict=False,
    ):
        if not cid or cid in exclude:
            continue
        if e is None or (isinstance(e, float) and pd.isna(e)) or float(e) <= 0:
            continue
        if not share_safe_under_deal(
            spot=s,
            edge_pct=e,
            rarity=r,
            set_name=sn,
            name=nm,
            supertype=st,
            price_change_7d_pct=c,
            spot_quarantine=qflag,
        ):
            continue
        ok.append((float(e), idx))

    ok.sort(key=lambda t: t[0], reverse=True)
    if not ok:
        return []
    pick_idx = [idx for _e, idx in ok[: int(need)]]
    frame = scoped.loc[pick_idx].copy()
    frame["_edge"] = [e for e, _idx in ok[: int(need)]]
    return _rows_from_frame(frame, side="UNDER")


def build_radar_preview(*, limit: int = 5) -> dict[str, Any]:
    """Public DOTD / hero: ≥$10 UNDER, top up so seats stay filled.

    Order: share-safe sure → relaxed sure → soft asking-below-good lean.
    """
    floor = float(SHARE_SAFE_MIN_UNDER_SPOT)
    need = max(1, min(8, int(limit)))
    pool = max(need, min(24, need * 4))

    primary = build_radar(
        min_edge=0,
        limit=pool,
        min_price=floor,
        share_safe=True,
    )
    under = list(primary.get("underpriced") or [])
    seen = {str(r.get("id")) for r in under if r.get("id")}
    relaxed = False

    if len(under) < need:
        secondary = build_radar(
            min_edge=0,
            limit=pool,
            min_price=floor,
            share_safe=False,
        )
        added = 0
        for row in secondary.get("underpriced") or []:
            cid = str(row.get("id") or "")
            if not cid or cid in seen:
                continue
            under.append(row)
            seen.add(cid)
            added += 1
            if len(under) >= need:
                break
        if added:
            relaxed = True

    if len(under) < need:
        soft = _soft_under_fill(
            need=need - len(under),
            exclude=seen,
            min_price=floor,
        )
        if soft:
            under.extend(soft)
            relaxed = True

    under = under[:need]
    return {
        "forecast_days": int(primary.get("forecast_days") or radar_defaults()["forecast_days"]),
        "under_total": max(int(primary.get("under_total") or 0), len(under)),
        "underpriced": under,
        "source": primary.get("source") or "empty",
        "relaxed": bool(relaxed),
    }

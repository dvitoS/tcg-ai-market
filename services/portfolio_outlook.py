"""Portfolio-native 30d outlook helpers (separate model artifact)."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from ai_xgboost import ARTIFACT_ID_30D, FEATURE_COLUMNS
from services.forecast import card_history, predict_horizon_return
from trading_signals import (
    PORTFOLIO_CONFORMAL_WIDTH_CAP,
    PORTFOLIO_GROWTH_FLOOR,
    PORTFOLIO_HORIZON_DAYS,
    PORTFOLIO_SIGNAL_BAND,
    SIGNAL_BUY,
    SIGNAL_HOLD,
    SIGNAL_SELL,
)

LOG = logging.getLogger("tcg.portfolio_outlook")

ACTION_ADD = "ADD"
ACTION_HOLD = "HOLD"
ACTION_TRIM = "TRIM"


def load_portfolio_model() -> tuple[Any, dict[str, Any]] | None:
    """Load 30d artifact when available."""
    try:
        from services.model_store import load_model_artifact

        loaded = load_model_artifact(ARTIFACT_ID_30D)
        if loaded is None:
            return None
        model, meta = loaded
        cols = list(meta.get("feature_columns") or [])
        if cols and cols != list(FEATURE_COLUMNS):
            LOG.warning("30d model feature mismatch — ignoring portfolio model.")
            return None
        return model, meta
    except Exception as exc:
        LOG.warning("load_portfolio_model failed: %s", exc)
        return None


def _meta_float(meta: dict[str, Any] | None, key: str) -> float | None:
    metrics = (meta or {}).get("metrics") or {}
    try:
        value = float(metrics.get(key))
    except (TypeError, ValueError):
        return None
    return value if value == value else None


def lot_action(
    *,
    expected_pct: float,
    conformal_ok: bool,
    growth_floor: float = PORTFOLIO_GROWTH_FLOOR,
) -> str:
    """Simple lot coach: ADD / TRIM / HOLD with conformal gate."""
    if not conformal_ok:
        return ACTION_HOLD
    if expected_pct >= float(growth_floor):
        return ACTION_ADD
    if expected_pct <= -float(growth_floor):
        return ACTION_TRIM
    return ACTION_HOLD


def enrich_portfolio_outlook(
    view: pd.DataFrame,
    history: pd.DataFrame,
    *,
    fallback_model=None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Attach 30d (preferred) horizon forecast + conformal + action per open lot.

    Falls back to the board 7d model if latest_30d is missing.
    """
    out = view.copy()
    info: dict[str, Any] = {
        "horizon_days": int(PORTFOLIO_HORIZON_DAYS),
        "using_30d": False,
        "conformal_q": None,
    }
    if out.empty:
        for col, dtype in (
            ("outlook_price", float),
            ("outlook_value", float),
            ("outlook_roi_pct", float),
            ("outlook_lo_pct", float),
            ("outlook_hi_pct", float),
            ("outlook_conformal_ok", bool),
            ("lot_action", object),
            ("week_price", float),
            ("week_value", float),
            ("week_roi_pct", float),
            ("is_top_ai", bool),
        ):
            out[col] = pd.Series(dtype=dtype)
        return out, info

    loaded = load_portfolio_model()
    if loaded is not None:
        model, meta = loaded
        info["using_30d"] = True
        info["horizon_days"] = int(
            _meta_float(meta, "horizon_days") or PORTFOLIO_HORIZON_DAYS
        )
        hold_band = float(_meta_float(meta, "hold_band") or PORTFOLIO_SIGNAL_BAND)
        width_cap = float(
            _meta_float(meta, "conformal_width_cap") or PORTFOLIO_CONFORMAL_WIDTH_CAP
        )
        q = _meta_float(meta, "conformal_q")
    elif fallback_model is not None:
        model, meta = fallback_model, {}
        info["horizon_days"] = 7
        hold_band = float(PORTFOLIO_SIGNAL_BAND)  # still use portfolio band for coach
        width_cap = float(PORTFOLIO_CONFORMAL_WIDTH_CAP)
        q = None
        LOG.info("Portfolio outlook falling back to 7d board model.")
    else:
        out["outlook_price"] = out["current_price"]
        out["outlook_value"] = out["quantity"] * out["outlook_price"]
        out["outlook_roi_pct"] = 0.0
        out["outlook_lo_pct"] = np.nan
        out["outlook_hi_pct"] = np.nan
        out["outlook_conformal_ok"] = False
        out["lot_action"] = ACTION_HOLD
        out["is_top_ai"] = False
        return out, info

    info["conformal_q"] = q
    prices: list[float] = []
    rois: list[float] = []
    los: list[float] = []
    his: list[float] = []
    oks: list[bool] = []
    actions: list[str] = []

    for lot in out.itertuples(index=False):
        spot = float(lot.current_price)
        series = card_history(history, str(lot.card_id))
        if (
            series.empty
            or pd.isna(getattr(lot, "rarity_encoded", np.nan))
            or pd.isna(getattr(lot, "supertype_encoded", np.nan))
        ):
            prices.append(spot)
            rois.append(0.0)
            los.append(float("nan"))
            his.append(float("nan"))
            oks.append(False)
            actions.append(ACTION_HOLD)
            continue
        pred_ret = predict_horizon_return(
            model,
            series["price"],
            float(lot.rarity_encoded),
            float(lot.supertype_encoded),
        )
        if pred_ret is None:
            prices.append(spot)
            rois.append(0.0)
            los.append(float("nan"))
            his.append(float("nan"))
            oks.append(False)
            actions.append(ACTION_HOLD)
            continue
        pred_ret = float(pred_ret)
        outlook_price = spot * (1.0 + pred_ret)
        roi_pct = pred_ret * 100.0
        if q is not None and q >= 0:
            lo = (pred_ret - q) * 100.0
            hi = (pred_ret + q) * 100.0
            width = (2.0 * q)
            crosses = (pred_ret - q) < 0.0 < (pred_ret + q)
            too_wide = width > width_cap
            conf_ok = not (crosses or too_wide)
        else:
            lo = float("nan")
            hi = float("nan")
            # Without conformal, only trust moves beyond portfolio band.
            conf_ok = abs(pred_ret) >= hold_band
        prices.append(float(outlook_price))
        rois.append(float(roi_pct))
        los.append(float(lo))
        his.append(float(hi))
        oks.append(bool(conf_ok))
        actions.append(
            lot_action(expected_pct=roi_pct, conformal_ok=bool(conf_ok))
        )

    out["outlook_price"] = prices
    out["outlook_value"] = out["quantity"].astype(float) * pd.Series(prices, index=out.index)
    out["outlook_roi_pct"] = rois
    out["outlook_lo_pct"] = los
    out["outlook_hi_pct"] = his
    out["outlook_conformal_ok"] = oks
    out["lot_action"] = actions
    # Holo / highlight: conformal-ok and strong expected move.
    out["is_top_ai"] = [
        bool(ok) and float(roi) >= float(PORTFOLIO_GROWTH_FLOOR)
        for ok, roi in zip(oks, rois, strict=True)
    ]
    # Keep week_* aliases for existing gallery/KPI paths during transition.
    out["week_price"] = out["outlook_price"]
    out["week_value"] = out["outlook_value"]
    out["week_roi_pct"] = out["outlook_roi_pct"]
    return out, info

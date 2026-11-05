"""Model trust panel — artifact calibration + proxy coverage + radar-call hits."""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from api.catalog_service import load_board
from api.demo_mode import demo_mode
from api.portfolio_service import load_history_for_cards
from services.model_store import ARTIFACT_ID, load_model_metrics

LOG = logging.getLogger("tcg.trust")


def _finite(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if math.isfinite(num) else None


def _metric_float(metrics: dict[str, Any], key: str) -> float | None:
    return _finite(metrics.get(key))


def _metric_int(metrics: dict[str, Any], key: str) -> int | None:
    try:
        value = metrics.get(key)
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _calibration_block(metrics: dict[str, Any]) -> dict[str, Any]:
    alpha = _metric_float(metrics, "conformal_alpha")
    return {
        "rmse": _metric_float(metrics, "rmse"),
        "r2": _metric_float(metrics, "r2"),
        "rmse_vs_naive": _metric_float(metrics, "rmse_vs_naive"),
        "direction_accuracy_pct": _metric_float(metrics, "direction_accuracy_pct"),
        "direction_n": _metric_int(metrics, "direction_n"),
        "conformal_q": _metric_float(metrics, "conformal_q"),
        "conformal_alpha": alpha,
        "conformal_width_cap": _metric_float(metrics, "conformal_width_cap"),
        "wf_folds": _metric_int(metrics, "wf_folds"),
        "wf_direction_accuracy_pct": _metric_float(metrics, "wf_direction_accuracy_pct"),
        "wf_rmse_vs_naive": _metric_float(metrics, "wf_rmse_vs_naive"),
    }


def _history_prices_by_card(history: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if history is None or history.empty:
        return {}
    hist = history.copy()
    hist["card_id"] = hist["card_id"].astype(str)
    hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
    hist["price"] = pd.to_numeric(hist["price"], errors="coerce")
    hist = hist.dropna(subset=["date", "price"])
    out: dict[str, pd.DataFrame] = {}
    for card_id, group in hist.groupby("card_id"):
        out[str(card_id)] = group.sort_values("date")
    return out


def _realized_pct(frame: pd.DataFrame, *, horizon_days: int) -> float | None:
    if frame is None or frame.empty or len(frame) < 2:
        return None
    end = frame.iloc[-1]
    end_date = pd.Timestamp(end["date"]).normalize()
    target = end_date - pd.DateOffset(days=int(horizon_days))
    prior = frame[frame["date"] <= target]
    if prior.empty:
        # Fall back to earliest point if history shorter than horizon.
        start = frame.iloc[0]
        gap = (end_date - pd.Timestamp(start["date"]).normalize()).days
        if gap < max(2, horizon_days // 2):
            return None
        start_px = float(start["price"])
    else:
        start_px = float(prior.iloc[-1]["price"])
    end_px = float(end["price"])
    if start_px <= 0:
        return None
    return (end_px - start_px) / start_px * 100.0


def _proxy_coverage(
    board: pd.DataFrame,
    by_card: dict[str, pd.DataFrame],
    *,
    horizon_days: int,
    sample_n: int,
    target_pct: float,
) -> dict[str, Any]:
    note = (
        "Proxy: today’s conformal band vs trailing realized return "
        f"over ~{horizon_days}d (not holdout calibration)."
    )
    empty = {
        "method": "unavailable",
        "target_pct": target_pct,
        "coverage_pct": None,
        "n": 0,
        "note": "No sure board rows with bands + history.",
    }
    if board is None or board.empty or not by_card:
        return empty

    sure = board.copy()
    if "conformal_ok" in sure.columns:
        sure = sure[sure["conformal_ok"].fillna(False).astype(bool)]
    if "confidence_ok" in sure.columns:
        sure = sure[sure["confidence_ok"].fillna(False).astype(bool)]
    sure = sure.dropna(subset=["pred_lo_pct", "pred_hi_pct"], how="any")
    if sure.empty:
        return empty

    # Prefer higher |edge| rows for a sharper trust sample.
    if "expected_change_pct" in sure.columns:
        sure = sure.assign(
            _abs=sure["expected_change_pct"].abs()
        ).sort_values("_abs", ascending=False)
    sample = sure.head(int(sample_n))

    covered = 0
    n = 0
    for _, row in sample.iterrows():
        card_id = str(row.get("id") or row.get("card_id") or "")
        hist = by_card.get(card_id)
        realized = _realized_pct(hist, horizon_days=horizon_days) if hist is not None else None
        lo = _finite(row.get("pred_lo_pct"))
        hi = _finite(row.get("pred_hi_pct"))
        if realized is None or lo is None or hi is None:
            continue
        n += 1
        if min(lo, hi) <= realized <= max(lo, hi):
            covered += 1

    if n <= 0:
        return empty
    return {
        "method": "proxy_trailing",
        "target_pct": target_pct,
        "coverage_pct": round(100.0 * covered / n, 2),
        "n": n,
        "note": note,
    }


def _radar_backtest(
    board: pd.DataFrame,
    by_card: dict[str, pd.DataFrame],
    *,
    horizon_days: int,
    lookback_days: int,
    sample_n: int,
) -> dict[str, Any]:
    del lookback_days  # Signals are current; history window is horizon_days.
    base = {
        "lookback_days": int(horizon_days),
        "horizon_days": int(horizon_days),
        "n": 0,
        "hit_rate_pct": None,
        "avg_move_pct": None,
        "under_n": 0,
        "over_n": 0,
        "method": "current_signals_vs_history",
    }
    if board is None or board.empty or not by_card:
        return base

    sure = board.copy()
    if "conformal_ok" in sure.columns:
        sure = sure[sure["conformal_ok"].fillna(False).astype(bool)]
    if "confidence_ok" in sure.columns:
        sure = sure[sure["confidence_ok"].fillna(False).astype(bool)]
    if sure.empty:
        return base

    under_rows = []
    over_rows = []
    for _, row in sure.iterrows():
        lo = _finite(row.get("pred_lo_pct"))
        hi = _finite(row.get("pred_hi_pct"))
        exp = _finite(row.get("expected_change_pct"))
        if lo is not None and lo > 0:
            under_rows.append(row)
        elif hi is not None and hi < 0:
            over_rows.append(row)
        elif exp is not None and exp >= 5:
            under_rows.append(row)
        elif exp is not None and exp <= -5:
            over_rows.append(row)

    under_rows = under_rows[: max(1, sample_n // 2)]
    over_rows = over_rows[: max(1, sample_n // 2)]
    hits = 0
    moves: list[float] = []
    under_n = 0
    over_n = 0

    for side, rows in (("UNDER", under_rows), ("OVER", over_rows)):
        for row in rows:
            card_id = str(row.get("id") or row.get("card_id") or "")
            hist = by_card.get(card_id)
            realized = _realized_pct(hist, horizon_days=horizon_days) if hist is not None else None
            if realized is None:
                continue
            moves.append(realized)
            if side == "UNDER":
                under_n += 1
                if realized > 0:
                    hits += 1
            else:
                over_n += 1
                if realized < 0:
                    hits += 1

    n = under_n + over_n
    base["n"] = n
    base["under_n"] = under_n
    base["over_n"] = over_n
    if n > 0:
        base["hit_rate_pct"] = round(100.0 * hits / n, 2)
        base["avg_move_pct"] = round(float(np.mean(moves)), 2) if moves else None
    return base


def build_trust_report(
    *,
    horizon_days: int = 7,
    lookback_days: int = 30,
    sample_n: int = 80,
) -> dict[str, Any]:
    horizon_days = max(3, min(int(horizon_days or 7), 30))
    lookback_days = max(7, min(int(lookback_days or 30), 120))
    sample_n = max(10, min(int(sample_n or 80), 120))

    meta = load_model_metrics(ARTIFACT_ID) or {}
    metrics = dict(meta.get("metrics") or {})
    calibration = _calibration_block(metrics)
    alpha = calibration.get("conformal_alpha")
    target_pct = round((1.0 - float(alpha)) * 100.0, 1) if alpha is not None else 80.0

    board, source = load_board()
    card_ids: list[str] = []
    if board is not None and not board.empty:
        id_col = "id" if "id" in board.columns else "card_id"
        card_ids = (
            board[id_col]
            .astype(str)
            .head(sample_n * 2)
            .tolist()
        )

    history = load_history_for_cards(card_ids) if card_ids else pd.DataFrame()
    by_card = _history_prices_by_card(history)

    coverage = _proxy_coverage(
        board if board is not None else pd.DataFrame(),
        by_card,
        horizon_days=horizon_days,
        sample_n=sample_n,
        target_pct=target_pct,
    )
    # Prefer holdout key if a future nightly writes it.
    holdout = _metric_float(metrics, "conformal_coverage_pct")
    if holdout is not None:
        coverage = {
            "method": "holdout",
            "target_pct": target_pct,
            "coverage_pct": holdout,
            "n": _metric_int(metrics, "direction_n") or 0,
            "note": "Holdout conformal coverage from the latest retrain.",
        }

    radar = _radar_backtest(
        board if board is not None else pd.DataFrame(),
        by_card,
        horizon_days=horizon_days,
        lookback_days=lookback_days,
        sample_n=sample_n,
    )

    return {
        "source": "demo" if demo_mode() and source == "demo" else (source or "empty"),
        "trained_at": meta.get("trained_at"),
        "artifact_id": meta.get("artifact_id") or ARTIFACT_ID,
        "horizon_days": horizon_days,
        "calibration": calibration,
        "conformal_coverage": coverage,
        "radar_backtest": radar,
    }

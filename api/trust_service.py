"""Model trust panel — artifact calibration + forward tip-ledger Radar hits."""

from __future__ import annotations

import logging
import math
from typing import Any

import pandas as pd

from api.catalog_service import load_board
from api.demo_mode import demo_mode
from api.portfolio_service import load_history_for_cards
from services.model_store import ARTIFACT_ID, load_model_metrics
from services.tip_ledger import record_sure_tips, score_forward_tips

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


def _sure_desk_frame(board: pd.DataFrame) -> pd.DataFrame:
    """Conformal + confidence filtered board (Soft Ink sure desk)."""
    if board is None or board.empty:
        return pd.DataFrame()
    sure = board.copy()
    if "conformal_ok" in sure.columns:
        sure = sure[sure["conformal_ok"].fillna(False).astype(bool)]
    if "confidence_ok" in sure.columns:
        sure = sure[sure["confidence_ok"].fillna(False).astype(bool)]
    return sure


def _tip_edge_pct(row: pd.Series) -> tuple[str | None, float | None]:
    """Return (UNDER|OVER|None, edge_pct) aligned with Radar ranking."""
    signal = str(row.get("signal") or "").upper()
    lo = _finite(row.get("pred_lo_pct"))
    hi = _finite(row.get("pred_hi_pct"))
    exp = _finite(row.get("expected_change_pct"))
    edge_u = lo if lo is not None else exp
    edge_o = hi if hi is not None else exp
    if signal == "BUY" or (edge_u is not None and edge_u > 0):
        return "UNDER", edge_u
    if signal == "SELL" or (edge_o is not None and edge_o < 0):
        return "OVER", edge_o
    if exp is not None and exp >= 5:
        return "UNDER", exp
    if exp is not None and exp <= -5:
        return "OVER", exp
    return None, None


def _split_sure_sides(
    sure: pd.DataFrame,
    *,
    sample_n: int,
    min_edge: float = 0.0,
) -> tuple[list[pd.Series], list[pd.Series]]:
    """Balanced UNDER/OVER sample from sure tips (respects Radar min edge %)."""
    under_rows: list[pd.Series] = []
    over_rows: list[pd.Series] = []
    if sure is None or sure.empty:
        return under_rows, over_rows

    floor = max(0.0, float(min_edge or 0.0))
    ranked = sure
    if "expected_change_pct" in sure.columns:
        ranked = sure.assign(_abs=sure["expected_change_pct"].abs()).sort_values(
            "_abs", ascending=False
        )

    for _, row in ranked.iterrows():
        side, edge = _tip_edge_pct(row)
        if side is None or edge is None:
            continue
        if floor > 0:
            if side == "UNDER" and edge < floor:
                continue
            if side == "OVER" and edge > -floor:
                continue
        if side == "UNDER":
            under_rows.append(row)
        else:
            over_rows.append(row)

    half = max(1, int(sample_n) // 2)
    return under_rows[:half], over_rows[:half]


def tips_payload_from_board(
    board: pd.DataFrame,
    *,
    sample_n: int = 80,
    min_edge: float = 0.0,
) -> list[dict[str, Any]]:
    """Serialize a balanced sure tip sample for the forward ledger."""
    sure = _sure_desk_frame(board)
    under_rows, over_rows = _split_sure_sides(
        sure, sample_n=sample_n, min_edge=min_edge
    )
    out: list[dict[str, Any]] = []
    for side, rows in (("UNDER", under_rows), ("OVER", over_rows)):
        for row in rows:
            cid = str(row.get("id") or row.get("card_id") or "").strip()
            if not cid:
                continue
            _side, edge = _tip_edge_pct(row)
            out.append(
                {
                    "card_id": cid,
                    "side": side,
                    "edge_pct": edge,
                    "pred_lo_pct": _finite(row.get("pred_lo_pct")),
                    "pred_hi_pct": _finite(row.get("pred_hi_pct")),
                }
            )
    return out


def record_radar_tips_from_board(
    board: pd.DataFrame | None = None,
    *,
    sample_n: int = 80,
) -> dict[str, Any]:
    """Snapshot today's sure desk into the tip ledger (nightly / trust refresh)."""
    if board is None:
        board, _source = load_board()
    if board is None or board.empty:
        return {"saved": False, "tips": 0, "reason": "empty_board"}
    # Record at edge floor 0 so Trust can filter later by min_edge.
    tips = tips_payload_from_board(board, sample_n=sample_n, min_edge=0.0)
    return record_sure_tips(tips)


def build_trust_report(
    *,
    horizon_days: int = 7,
    lookback_days: int = 30,
    sample_n: int = 80,
    min_edge: float = 0.0,
    record_tips: bool = True,
) -> dict[str, Any]:
    horizon_days = max(3, min(int(horizon_days or 7), 30))
    lookback_days = max(7, min(int(lookback_days or 30), 120))
    sample_n = max(10, min(int(sample_n or 80), 120))
    min_edge = max(0.0, min(float(min_edge or 0.0), 100.0))
    del lookback_days  # Forward ledger uses horizon_days only.

    meta = load_model_metrics(ARTIFACT_ID) or {}
    metrics = dict(meta.get("metrics") or {})
    calibration = _calibration_block(metrics)
    alpha = calibration.get("conformal_alpha")
    target_pct = round((1.0 - float(alpha)) * 100.0, 1) if alpha is not None else 80.0

    board, source = load_board()
    board_frame = board if board is not None else pd.DataFrame()

    if record_tips and not board_frame.empty:
        try:
            recorded = record_radar_tips_from_board(board_frame, sample_n=sample_n)
            LOG.info("Trust tip ledger record: %s", recorded)
        except Exception as exc:
            LOG.warning("Trust tip ledger record failed: %s", exc)

    from services.tip_ledger import load_tip_ledger

    ledger = load_tip_ledger()
    card_ids = sorted(
        {
            str(t.get("card_id") or "").strip()
            for t in ledger
            if str(t.get("card_id") or "").strip()
        }
    )
    # Also include today's sure tips so history is warm for upcoming scores.
    sure = _sure_desk_frame(board_frame)
    under_rows, over_rows = _split_sure_sides(
        sure, sample_n=sample_n, min_edge=min_edge
    )
    for row in under_rows + over_rows:
        cid = str(row.get("id") or row.get("card_id") or "").strip()
        if cid:
            card_ids.append(cid)
    seen: set[str] = set()
    ordered_ids: list[str] = []
    for cid in card_ids:
        if cid not in seen:
            seen.add(cid)
            ordered_ids.append(cid)

    history = load_history_for_cards(ordered_ids) if ordered_ids else pd.DataFrame()
    by_card = _history_prices_by_card(history)

    radar = score_forward_tips(
        by_card,
        horizon_days=horizon_days,
        min_edge=min_edge,
    )

    holdout = _metric_float(metrics, "conformal_coverage_pct")
    if holdout is not None:
        coverage = {
            "method": "holdout",
            "target_pct": target_pct,
            "coverage_pct": holdout,
            "n": _metric_int(metrics, "direction_n") or 0,
            "note": "Holdout conformal coverage from the latest retrain.",
        }
    elif radar.get("coverage_n"):
        coverage = {
            "method": "forward_tip_ledger",
            "target_pct": target_pct,
            "coverage_pct": radar.get("coverage_pct"),
            "n": int(radar.get("coverage_n") or 0),
            "note": (
                "Forward band coverage: tip-time conformal band vs realized "
                f"{horizon_days}d move after the tip."
            ),
        }
    else:
        coverage = {
            "method": "unavailable",
            "target_pct": target_pct,
            "coverage_pct": None,
            "n": 0,
            "note": (
                "No forward band coverage yet — waiting for tip ledger rows "
                f"older than {horizon_days}d."
            ),
        }

    return {
        "source": "demo" if demo_mode() and source == "demo" else (source or "empty"),
        "trained_at": meta.get("trained_at"),
        "artifact_id": meta.get("artifact_id") or ARTIFACT_ID,
        "horizon_days": horizon_days,
        "min_edge": min_edge,
        "calibration": calibration,
        "conformal_coverage": coverage,
        "radar_backtest": radar,
    }

"""Public Soft Ink market pulse — board breadth + 7d movers for the landing desk."""

from __future__ import annotations

from typing import Any

import pandas as pd

from api.catalog_service import load_board, row_to_card
from api.radar_service import build_radar


def _f(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _movers(frame: pd.DataFrame, *, ascending: bool, limit: int) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    col = "price_change_7d_pct"
    if col not in frame.columns:
        return []
    scoped = frame.dropna(subset=[col]).copy()
    if "price" in scoped.columns:
        scoped = scoped[_f(scoped["price"]).fillna(0) >= 5.0]
    if scoped.empty:
        return []
    scoped = scoped.sort_values(col, ascending=ascending, na_position="last")
    out: list[dict[str, Any]] = []
    for _, row in scoped.head(int(limit)).iterrows():
        card = row_to_card(row)
        out.append(
            {
                "id": card["id"],
                "name": card["name"],
                "set_name": card.get("set_name"),
                "image_url": card.get("image_url"),
                "price": card.get("price"),
                "price_change_7d_pct": card.get("price_change_7d_pct"),
                "signal": card.get("signal"),
            }
        )
    return out


def build_market_pulse(*, mover_limit: int = 5) -> dict[str, Any]:
    board, source = load_board()
    empty = {
        "source": source,
        "board_total": 0,
        "sure_under": 0,
        "sure_over": 0,
        "signals": {},
        "median_change_7d_pct": None,
        "rising_n": 0,
        "falling_n": 0,
        "flat_n": 0,
        "observed_n": 0,
        "rising_share_pct": None,
        "risers": [],
        "fallers": [],
    }
    if board is None or board.empty:
        return empty

    signals: dict[str, int] = {}
    if "signal" in board.columns:
        signals = {
            str(k): int(v)
            for k, v in board["signal"].fillna("HOLD").astype(str).str.upper().value_counts().items()
        }

    change = (
        _f(board["price_change_7d_pct"])
        if "price_change_7d_pct" in board.columns
        else pd.Series(dtype=float)
    )
    observed = change.dropna()
    rising_n = int((observed > 0.15).sum()) if not observed.empty else 0
    falling_n = int((observed < -0.15).sum()) if not observed.empty else 0
    flat_n = int(len(observed) - rising_n - falling_n) if not observed.empty else 0
    observed_n = int(len(observed))
    median = float(observed.median()) if not observed.empty else None
    rising_share = (
        float(rising_n / observed_n * 100.0) if observed_n > 0 else None
    )

    sure_under = 0
    sure_over = 0
    try:
        radar = build_radar(min_edge=0, limit=1, share_safe=True)
        sure_under = int(radar.get("under_total") or 0)
        sure_over = int(radar.get("over_total") or 0)
    except Exception:
        # Pulse should still render when Radar gates throw; breadth alone is enough.
        if "signal" in board.columns and "confidence_ok" in board.columns:
            sure = board[board["confidence_ok"].fillna(False).astype(bool)]
            sure_under = int((sure["signal"].astype(str).str.upper() == "BUY").sum())
            sure_over = int((sure["signal"].astype(str).str.upper() == "SELL").sum())

    limit = max(1, min(8, int(mover_limit)))
    return {
        "source": source,
        "board_total": int(len(board)),
        "sure_under": sure_under,
        "sure_over": sure_over,
        "signals": signals,
        "median_change_7d_pct": median,
        "rising_n": rising_n,
        "falling_n": falling_n,
        "flat_n": flat_n,
        "observed_n": observed_n,
        "rising_share_pct": rising_share,
        "risers": _movers(board, ascending=False, limit=limit),
        "fallers": _movers(board, ascending=True, limit=limit),
    }

"""AI Scanner board built from precomputed market_quotes (no live XGBoost)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from api.catalog_service import filter_board, load_board, row_to_card
from trading_signals import FORECAST_DAYS, SCANNER_GROWTH_FLOOR


def scanner_defaults() -> dict[str, Any]:
    return {
        "forecast_days": int(FORECAST_DAYS),
        "growth_floor": float(SCANNER_GROWTH_FLOOR),
    }


def build_scanner(
    *,
    q: str | None = None,
    set_name: str | None = None,
    rarity: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_growth: float = SCANNER_GROWTH_FLOOR,
    limit: int = 24,
) -> dict[str, Any]:
    board, source = load_board()
    defaults = scanner_defaults()
    if board is None or board.empty:
        return {
            **defaults,
            "source": source,
            "scoped": 0,
            "opportunities": [],
            "warnings": [],
            "opp_total": 0,
            "warn_total": 0,
        }

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
            **defaults,
            "source": source,
            "scoped": 0,
            "opportunities": [],
            "warnings": [],
            "opp_total": 0,
            "warn_total": 0,
            "min_growth": float(min_growth),
        }

    change = pd.to_numeric(scoped.get("expected_change_pct"), errors="coerce")
    scoped = scoped.assign(_roi=change)
    opportunities = (
        scoped.loc[scoped["_roi"].fillna(-999) >= float(min_growth)]
        .sort_values("_roi", ascending=False)
        .reset_index(drop=True)
    )
    warnings = (
        scoped.loc[scoped["_roi"].fillna(0) < 0]
        .sort_values("_roi", ascending=True)
        .reset_index(drop=True)
    )

    def _rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for _, row in frame.head(int(limit)).iterrows():
            card = row_to_card(row)
            price = card.get("price")
            predicted = card.get("predicted_price")
            roi = card.get("expected_change_pct")
            out.append(
                {
                    **card,
                    "current_price": price,
                    "ai_target_price": predicted,
                    "expected_roi_pct": roi,
                }
            )
        return out

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
        "min_growth": float(min_growth),
        "sets": sets,
        "rarities": rarities,
        "opportunities": _rows(opportunities),
        "warnings": _rows(warnings),
        "opp_total": int(len(opportunities)),
        "warn_total": int(len(warnings)),
    }

"""AI explainability + simple scanner backtest helpers (Sprint D)."""

from __future__ import annotations

from typing import Any

import pandas as pd


def series_confidence(*, points: int, used_db_fallback: bool = False) -> dict[str, Any]:
    """Gate trading-signal confidence from data quality."""
    if points < 8:
        return {
            "level": "low",
            "ok": False,
            "reason": "Series shorter than 8 days — lag features are incomplete.",
        }
    if used_db_fallback:
        return {
            "level": "medium",
            "ok": True,
            "reason": "Live JustTCG history was empty; forecast uses saved market history.",
        }
    if points < 20:
        return {
            "level": "medium",
            "ok": True,
            "reason": "Short series — treat the signal as directional only.",
        }
    return {
        "level": "high",
        "ok": True,
        "reason": "Enough history for next-day lag features.",
    }


def explain_features(
    *,
    lags: dict[str, float],
    last_price: float,
    predicted: float,
    hold_band: float,
    horizon_days: int = 1,
) -> list[tuple[str, str]]:
    """Human-readable feature dump for the detail panel."""
    lag1 = float(lags.get("price_lag_1", last_price))
    roll7 = float(lags.get("rolling_mean_7", last_price))
    vs_roll = ((last_price - roll7) / roll7 * 100.0) if roll7 else 0.0
    move = ((predicted - last_price) / last_price * 100.0) if last_price else 0.0
    return [
        ("Horizon", f"{horizon_days} trading day(s)"),
        ("Yesterday close", f"{lag1:.4f}"),
        ("7-day average", f"{roll7:.4f}"),
        ("Spot vs 7d avg", f"{vs_roll:+.2f}%"),
        ("Expected move", f"{move:+.2f}%"),
        ("HOLD band", f"±{hold_band * 100:.2f}%"),
        ("Disclaimer", "Not financial advice — model output only."),
    ]


def scanner_backtest(
    history: pd.DataFrame,
    *,
    lookback_days: int = 7,
    growth_floor: float = 10.0,
    top_n: int = 20,
) -> pd.DataFrame:
    """Naive backtest: cards whose trailing lookback return was ≥ floor, then forward week.

    This is a transparency check (momentum persistence), not the live XGBoost score.
    """
    if history.empty or "card_id" not in history.columns:
        return pd.DataFrame()

    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["card_id", "date"])
    rows: list[dict[str, Any]] = []
    for card_id, group in frame.groupby("card_id"):
        g = group.dropna(subset=["price"]).sort_values("date")
        if len(g) < lookback_days + 2:
            continue
        past = g.iloc[-(lookback_days + 1)]
        now = g.iloc[-1]
        past_price = float(past["price"])
        now_price = float(now["price"])
        if past_price <= 0:
            continue
        trailing = (now_price - past_price) / past_price * 100.0
        # Synthetic "would have held for lookback" forward from past→now already measured.
        rows.append(
            {
                "id": str(card_id),
                "name": str(g["name"].iloc[-1]) if "name" in g.columns else str(card_id),
                "set_name": str(g["set_name"].iloc[-1]) if "set_name" in g.columns else "",
                "trailing_pct": trailing,
                "start_price": past_price,
                "end_price": now_price,
            }
        )
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out = out.loc[out["trailing_pct"] >= float(growth_floor)].sort_values(
        "trailing_pct", ascending=False
    )
    return out.head(int(top_n)).reset_index(drop=True)


def backtest_summary(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {"n": 0, "hit_rate": 0.0, "avg_return": 0.0, "median_return": 0.0}
    wins = int((frame["trailing_pct"] > 0).sum())
    return {
        "n": float(len(frame)),
        "hit_rate": wins / len(frame) * 100.0,
        "avg_return": float(frame["trailing_pct"].mean()),
        "median_return": float(frame["trailing_pct"].median()),
    }

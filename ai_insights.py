"""AI explainability + scanner backtest helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd


def series_confidence(*, points: int, used_db_fallback: bool = False) -> dict[str, Any]:
    """Gate trading-signal confidence from data quality."""
    if points < 8:
        return {
            "level": "low",
            "ok": False,
            "reason_key": "conf_short",
            "reason": "Series shorter than 8 days — lag features are incomplete.",
        }
    if used_db_fallback:
        return {
            "level": "low",
            "ok": True,
            "reason_key": "conf_fallback",
            "reason": "Live JustTCG NM was empty — forecast uses saved DB history; treat signal cautiously.",
        }
    if points < 20:
        return {
            "level": "medium",
            "ok": True,
            "reason_key": "conf_medium",
            "reason": "Short series — treat the signal as directional only.",
        }
    return {
        "level": "high",
        "ok": True,
        "reason_key": "conf_high",
        "reason": "Enough history for next-day lag features.",
    }


def confidence_by_card(history: pd.DataFrame) -> pd.DataFrame:
    """Per-card confidence from history length (no live-fallback flag)."""
    if history is None or history.empty or "card_id" not in history.columns:
        return pd.DataFrame(columns=["id", "history_points", "confidence_ok", "confidence_level"])
    counts = (
        history.dropna(subset=["price"])
        .groupby(history["card_id"].astype(str), sort=False)
        .size()
        .rename("history_points")
        .reset_index()
        .rename(columns={"card_id": "id"})
    )
    levels: list[str] = []
    oks: list[bool] = []
    for n in counts["history_points"].astype(int):
        conf = series_confidence(points=int(n), used_db_fallback=False)
        levels.append(str(conf["level"]))
        oks.append(bool(conf["ok"]))
    counts["confidence_level"] = levels
    counts["confidence_ok"] = oks
    return counts


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
    forward_days: int = 7,
    growth_floor: float = 10.0,
    top_n: int = 20,
) -> pd.DataFrame:
    """Point-in-time momentum check: trailing ≥ floor, then measure forward return.

    Not the live XGBoost score — transparency for “did strong movers keep moving?”
    """
    if history.empty or "card_id" not in history.columns:
        return pd.DataFrame()

    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date", "price"]).sort_values(["card_id", "date"])
    need = int(lookback_days) + int(forward_days) + 1
    rows: list[dict[str, Any]] = []

    for card_id, group in frame.groupby("card_id"):
        g = group.sort_values("date").reset_index(drop=True)
        if len(g) < need:
            continue
        # Anchor: last bar where a full forward window still exists.
        anchor_idx = len(g) - 1 - int(forward_days)
        start_idx = anchor_idx - int(lookback_days)
        if start_idx < 0 or anchor_idx <= start_idx:
            continue
        past = g.iloc[start_idx]
        anchor = g.iloc[anchor_idx]
        future = g.iloc[anchor_idx + int(forward_days)]
        past_price = float(past["price"])
        anchor_price = float(anchor["price"])
        future_price = float(future["price"])
        if past_price <= 0 or anchor_price <= 0:
            continue
        trailing = (anchor_price - past_price) / past_price * 100.0
        if trailing < float(growth_floor):
            continue
        forward = (future_price - anchor_price) / anchor_price * 100.0
        rows.append(
            {
                "id": str(card_id),
                "name": str(g["name"].iloc[-1]) if "name" in g.columns else str(card_id),
                "set_name": str(g["set_name"].iloc[-1]) if "set_name" in g.columns else "",
                "trailing_pct": trailing,
                "forward_pct": forward,
                "start_price": past_price,
                "anchor_price": anchor_price,
                "end_price": future_price,
            }
        )

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows).sort_values("forward_pct", ascending=False)
    return out.head(int(top_n)).reset_index(drop=True)


def backtest_summary(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {"n": 0, "hit_rate": 0.0, "avg_return": 0.0, "median_return": 0.0}
    col = "forward_pct" if "forward_pct" in frame.columns else "trailing_pct"
    wins = int((frame[col] > 0).sum())
    return {
        "n": float(len(frame)),
        "hit_rate": wins / len(frame) * 100.0,
        "avg_return": float(frame[col].mean()),
        "median_return": float(frame[col].median()),
    }

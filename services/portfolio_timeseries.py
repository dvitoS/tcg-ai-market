"""Daily invested cost basis vs mark-to-market for portfolio lots."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _parse_lot_date(value) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).normalize()


def portfolio_timeseries(
    lots: pd.DataFrame,
    history: pd.DataFrame,
    *,
    max_days: int = 120,
) -> pd.DataFrame:
    """Daily invested cost basis vs mark-to-market value for held lots."""
    if lots is None or lots.empty or history is None or history.empty:
        return pd.DataFrame(columns=["date", "invested", "market_value"])

    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
    hist = hist.dropna(subset=["date", "card_id", "price"])
    hist["card_id"] = hist["card_id"].astype(str)
    hist["price"] = pd.to_numeric(hist["price"], errors="coerce")
    hist = hist.dropna(subset=["price"])
    if hist.empty:
        return pd.DataFrame(columns=["date", "invested", "market_value"])

    price_wide = (
        hist.sort_values("date")
        .pivot_table(index="date", columns="card_id", values="price", aggfunc="last")
        .sort_index()
        .ffill()
    )

    lot_rows: list[dict] = []
    for row in lots.itertuples(index=False):
        start = _parse_lot_date(getattr(row, "purchase_date", None))
        if start is None:
            continue
        status = str(getattr(row, "status", "open") or "open").lower()
        end = _parse_lot_date(getattr(row, "sale_date", None)) if status == "sold" else None
        if status == "sold" and end is None:
            continue
        lot_rows.append(
            {
                "card_id": str(row.card_id),
                "qty": float(row.quantity or 0),
                "cost": float(row.purchase_price or 0),
                "start": start,
                "end": end,
            }
        )
    if not lot_rows:
        return pd.DataFrame(columns=["date", "invested", "market_value"])

    start_date = min(r["start"] for r in lot_rows)
    end_date = pd.Timestamp.today().normalize()
    hist_start = pd.Timestamp(price_wide.index.min()).normalize()
    hist_end = pd.Timestamp(price_wide.index.max()).normalize()
    start_date = max(start_date, hist_start)
    end_date = min(end_date, hist_end)
    if end_date < start_date:
        return pd.DataFrame(columns=["date", "invested", "market_value"])

    all_days = pd.date_range(start_date, end_date, freq="D")
    if len(all_days) > max_days:
        all_days = all_days[-max_days:]

    price_daily = price_wide.reindex(price_wide.index.union(all_days)).sort_index().ffill()
    price_daily = price_daily.reindex(all_days)

    invested_vals: list[float] = []
    value_vals: list[float] = []
    for day in all_days:
        invested = 0.0
        value = 0.0
        for lot in lot_rows:
            if lot["start"] > day:
                continue
            if lot["end"] is not None and day > lot["end"]:
                continue
            invested += lot["qty"] * lot["cost"]
            px = (
                price_daily.at[day, lot["card_id"]]
                if lot["card_id"] in price_daily.columns
                else np.nan
            )
            if px is not None and not pd.isna(px):
                value += lot["qty"] * float(px)
            else:
                value += lot["qty"] * lot["cost"]
        invested_vals.append(invested)
        value_vals.append(value)

    return pd.DataFrame(
        {
            "date": all_days,
            "invested": invested_vals,
            "market_value": value_vals,
        }
    )

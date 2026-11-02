"""Persist / load precomputed market_quotes board."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

LOG = logging.getLogger("tcg.quotes_store")

TABLE = "market_quotes"

QUOTE_COLUMNS = [
    "id",
    "name",
    "set_name",
    "rarity",
    "supertype",
    "price",
    "market_price",
    "predicted_price",
    "expected_change_pct",
    "signal",
    "confidence_ok",
    "confidence_level",
    "history_points",
]


def _rows_from_quotes(quotes: pd.DataFrame) -> list[dict[str, Any]]:
    if quotes is None or quotes.empty:
        return []
    frame = quotes.copy()
    if "id" not in frame.columns and "card_id" in frame.columns:
        frame["id"] = frame["card_id"]
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        card_id = str(row.get("id") or "").strip()
        if not card_id:
            continue
        conf_ok = row.get("confidence_ok")
        if conf_ok is None or (isinstance(conf_ok, float) and pd.isna(conf_ok)):
            conf_ok = True
        payload = {
            "card_id": card_id,
            "name": str(row.get("name") or "") or None,
            "set_name": str(row.get("set_name") or "") or None,
            "rarity": str(row.get("rarity") or "") or None,
            "supertype": str(row.get("supertype") or "") or None,
            "price": _float_or_none(row.get("price")),
            "market_price": _float_or_none(row.get("market_price")),
            "predicted_price": _float_or_none(row.get("predicted_price")),
            "expected_change_pct": _float_or_none(row.get("expected_change_pct")),
            "signal": str(row.get("signal") or "") or None,
            "confidence_ok": bool(conf_ok),
            "confidence_level": str(row.get("confidence_level") or "") or None,
            "history_points": int(row.get("history_points") or 0),
            "updated_at": now,
        }
        rows.append(payload)
    return rows


def _float_or_none(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def save_market_quotes(quotes: pd.DataFrame) -> int:
    """Replace-style upsert of the catalog board."""
    rows = _rows_from_quotes(quotes)
    if not rows:
        return 0
    try:
        from database import _chunked, get_supabase

        client = get_supabase()
        saved = 0
        for chunk in _chunked(rows, size=200):
            client.table(TABLE).upsert(chunk, on_conflict="card_id").execute()
            saved += len(chunk)
        return saved
    except Exception as exc:
        LOG.warning("save_market_quotes failed: %s", exc)
        return 0


def load_market_quotes() -> pd.DataFrame | None:
    """Return board with UI column names, or None if empty / unavailable."""
    try:
        from database import fetch_all

        rows = fetch_all(
            TABLE,
            "card_id,name,set_name,rarity,supertype,price,market_price,"
            "predicted_price,expected_change_pct,signal,confidence_ok,"
            "confidence_level,history_points,updated_at",
            order="name",
        )
    except Exception as exc:
        LOG.warning("load_market_quotes failed: %s", exc)
        return None
    if not rows:
        return None
    frame = pd.DataFrame(rows)
    frame = frame.rename(columns={"card_id": "id"})
    for col in (
        "price",
        "market_price",
        "predicted_price",
        "expected_change_pct",
    ):
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    if "confidence_ok" in frame.columns:
        frame["confidence_ok"] = frame["confidence_ok"].fillna(True).astype(bool)
    if "history_points" in frame.columns:
        frame["history_points"] = (
            pd.to_numeric(frame["history_points"], errors="coerce").fillna(0).astype(int)
        )
    return frame

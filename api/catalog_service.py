"""Catalog board loading for the HTTP API (no Streamlit)."""

from __future__ import annotations

import logging
import math
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from pokemon_tcg_client import pokemontcg_image_url

LOG = logging.getLogger("kestrel.api.catalog")

Source = Literal["supabase", "demo", "empty"]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEED_DB = PROJECT_ROOT / "data" / "seed_tcg_market.db"


def _image_for(card_id: str, existing: str | None = None) -> str | None:
    if existing and str(existing).strip():
        return str(existing).strip()
    return pokemontcg_image_url(str(card_id))


def _frame_from_quotes(quotes: pd.DataFrame) -> pd.DataFrame:
    frame = quotes.copy()
    if "id" not in frame.columns and "card_id" in frame.columns:
        frame["id"] = frame["card_id"]
    frame["id"] = frame["id"].astype(str)
    if "image_url" not in frame.columns:
        frame["image_url"] = frame["id"].map(lambda cid: _image_for(cid))
    else:
        frame["image_url"] = [
            _image_for(str(cid), url if isinstance(url, str) else None)
            for cid, url in zip(frame["id"], frame["image_url"], strict=True)
        ]
    if "price" not in frame.columns and "market_price" in frame.columns:
        frame["price"] = frame["market_price"]
    for col in (
        "price",
        "market_price",
        "predicted_price",
        "expected_change_pct",
        "price_change_7d_pct",
        "pred_lo_pct",
        "pred_hi_pct",
    ):
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    if "confidence_ok" in frame.columns:
        frame["confidence_ok"] = frame["confidence_ok"].fillna(True).astype(bool)
    else:
        frame["confidence_ok"] = True
    if "conformal_ok" in frame.columns:
        frame["conformal_ok"] = frame["conformal_ok"].fillna(True).astype(bool)
    else:
        frame["conformal_ok"] = True
    if "history_points" in frame.columns:
        frame["history_points"] = (
            pd.to_numeric(frame["history_points"], errors="coerce").fillna(0).astype(int)
        )
    else:
        frame["history_points"] = 0
    return frame


def _load_demo_frame() -> pd.DataFrame | None:
    if not SEED_DB.is_file():
        return None
    try:
        with sqlite3.connect(SEED_DB) as conn:
            cards = pd.read_sql_query(
                "SELECT id, name, set_name, rarity, supertype, market_price, image_url "
                "FROM cards ORDER BY market_price DESC",
                conn,
            )
            hist = pd.read_sql_query(
                "SELECT card_id, price, date FROM price_history ORDER BY date",
                conn,
            )
    except Exception as exc:
        LOG.warning("demo seed load failed: %s", exc)
        return None
    if cards.empty:
        return None

    # Synthetic 7d change + signal from last two history points per card.
    changes: dict[str, float] = {}
    if not hist.empty:
        hist["price"] = pd.to_numeric(hist["price"], errors="coerce")
        hist = hist.dropna(subset=["price"])
        for card_id, group in hist.groupby("card_id"):
            tail = group.tail(8)
            if len(tail) < 2:
                continue
            first = float(tail.iloc[0]["price"])
            last = float(tail.iloc[-1]["price"])
            if first > 0:
                changes[str(card_id)] = ((last - first) / first) * 100.0

    rows: list[dict[str, Any]] = []
    for _, row in cards.iterrows():
        card_id = str(row["id"])
        price = float(row["market_price"] or 0.0)
        change = changes.get(card_id)
        if change is None:
            signal = "HOLD"
        elif change >= 3.0:
            signal = "BUY"
        elif change <= -3.0:
            signal = "SELL"
        else:
            signal = "HOLD"
        predicted = price * (1.0 + (change or 0.0) / 100.0) if price else None
        rows.append(
            {
                "id": card_id,
                "name": row["name"],
                "set_name": row.get("set_name"),
                "rarity": row.get("rarity"),
                "supertype": row.get("supertype"),
                "price": price,
                "market_price": price,
                "predicted_price": predicted,
                "expected_change_pct": change,
                "price_change_7d_pct": change,
                "signal": signal,
                "confidence_ok": True,
                "conformal_ok": True,
                "confidence_level": "demo",
                "history_points": int((hist["card_id"] == card_id).sum()) if not hist.empty else 0,
                "image_url": _image_for(card_id, row.get("image_url")),
                "pred_lo_pct": (change - 2.0) if change is not None else None,
                "pred_hi_pct": (change + 2.0) if change is not None else None,
            }
        )
    return _frame_from_quotes(pd.DataFrame(rows))


@lru_cache(maxsize=1)
def load_board() -> tuple[pd.DataFrame, Source]:
    """Return (board, source). Prefers live market_quotes; falls back to seed demo."""
    try:
        from services.quotes_store import load_market_quotes

        quotes = load_market_quotes()
        if quotes is not None and not quotes.empty:
            return _frame_from_quotes(quotes), "supabase"
    except Exception as exc:
        LOG.info("market_quotes unavailable (%s); trying demo seed", exc)

    demo = _load_demo_frame()
    if demo is not None and not demo.empty:
        return demo, "demo"
    return pd.DataFrame(), "empty"


def clear_board_cache() -> None:
    load_board.cache_clear()


def price_bounds(series: pd.Series, *, fallback_hi: float = 100.0) -> tuple[float, float]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return 0.0, float(fallback_hi)
    lo = float(math.floor(values.min() * 100) / 100)
    hi = float(math.ceil(values.max() * 100) / 100)
    if hi <= lo:
        hi = lo + 1.0
    return max(0.0, lo), hi


def filter_board(
    board: pd.DataFrame,
    *,
    q: str | None = None,
    set_name: str | None = None,
    signal: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    mode: Literal["browse", "signals"] = "browse",
) -> pd.DataFrame:
    if board is None or board.empty:
        return board
    frame = board.copy()
    if mode == "signals" and "signal" in frame.columns:
        # Prefer conformal / confidence-ok rows when present.
        if "confidence_ok" in frame.columns:
            sure = frame[frame["confidence_ok"]]
            if not sure.empty:
                frame = sure
    if q:
        needle = q.strip().lower()
        if needle:
            mask = (
                frame["name"].astype(str).str.lower().str.contains(needle, na=False)
                | frame.get("set_name", pd.Series("", index=frame.index))
                .astype(str)
                .str.lower()
                .str.contains(needle, na=False)
                | frame["id"].astype(str).str.lower().str.contains(needle, na=False)
            )
            frame = frame[mask]
    if set_name and set_name.strip() and set_name.strip().lower() not in {"all", "all sets"}:
        frame = frame[
            frame.get("set_name", pd.Series("", index=frame.index)).astype(str) == set_name.strip()
        ]
    if signal and signal.strip() and signal.strip().upper() != "ALL":
        frame = frame[frame.get("signal", pd.Series("", index=frame.index)).astype(str).str.upper() == signal.strip().upper()]
    if min_price is not None and "price" in frame.columns:
        frame = frame[pd.to_numeric(frame["price"], errors="coerce").fillna(0) >= float(min_price)]
    if max_price is not None and "price" in frame.columns:
        frame = frame[pd.to_numeric(frame["price"], errors="coerce").fillna(0) <= float(max_price)]
    return frame.reset_index(drop=True)


def row_to_card(row: pd.Series | dict[str, Any]) -> dict[str, Any]:
    get = row.get if isinstance(row, dict) else row.get

    def _f(key: str) -> float | None:
        val = get(key)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def _s(key: str) -> str | None:
        val = get(key)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        text = str(val).strip()
        return text or None

    card_id = str(get("id") or get("card_id") or "")
    return {
        "id": card_id,
        "name": str(get("name") or ""),
        "set_name": _s("set_name"),
        "rarity": _s("rarity"),
        "supertype": _s("supertype"),
        "price": _f("price"),
        "market_price": _f("market_price"),
        "predicted_price": _f("predicted_price"),
        "expected_change_pct": _f("expected_change_pct"),
        "price_change_7d_pct": _f("price_change_7d_pct"),
        "signal": _s("signal"),
        "confidence_ok": bool(get("confidence_ok") if get("confidence_ok") is not None else True),
        "conformal_ok": bool(get("conformal_ok") if get("conformal_ok") is not None else True),
        "confidence_level": _s("confidence_level"),
        "history_points": int(get("history_points") or 0),
        "image_url": _s("image_url") or _image_for(card_id),
    }


def board_meta(board: pd.DataFrame, source: Source) -> dict[str, Any]:
    if board is None or board.empty:
        return {
            "total": 0,
            "sets": [],
            "signals": {},
            "price_min": 0.0,
            "price_max": 100.0,
            "source": source,
        }
    sets = sorted(
        {
            str(s)
            for s in board.get("set_name", pd.Series(dtype=str)).dropna().astype(str).tolist()
            if str(s).strip()
        }
    )
    signals: dict[str, int] = {}
    if "signal" in board.columns:
        signals = {
            str(k): int(v)
            for k, v in board["signal"].fillna("HOLD").astype(str).str.upper().value_counts().items()
        }
    lo, hi = price_bounds(board["price"] if "price" in board.columns else pd.Series(dtype=float))
    return {
        "total": int(len(board)),
        "sets": sets,
        "signals": signals,
        "price_min": lo,
        "price_max": hi,
        "source": source,
    }


def load_card_history(card_id: str, *, limit: int = 180) -> list[dict[str, Any]]:
    card_id = str(card_id).strip()
    if not card_id:
        return []
    try:
        from database_catalog import load_history_frame

        hist = load_history_frame(card_ids=[card_id])
        if hist is not None and not hist.empty:
            frame = hist.sort_values("date").tail(limit)
            points: list[dict[str, Any]] = []
            for _, row in frame.iterrows():
                try:
                    points.append(
                        {
                            "date": str(row["date"])[:10],
                            "price": float(row["price"]),
                        }
                    )
                except (TypeError, ValueError, KeyError):
                    continue
            if points:
                return points
    except Exception as exc:
        LOG.info("history from supabase failed for %s: %s", card_id, exc)

    if not SEED_DB.is_file():
        return []
    try:
        with sqlite3.connect(SEED_DB) as conn:
            rows = conn.execute(
                "SELECT date, price FROM price_history WHERE card_id = ? ORDER BY date",
                (card_id,),
            ).fetchall()
        return [{"date": str(d)[:10], "price": float(p)} for d, p in rows[-limit:]]
    except Exception as exc:
        LOG.warning("demo history failed for %s: %s", card_id, exc)
        return []

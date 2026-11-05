"""Portfolio + watchlist service (JWT Supabase or in-memory demo)."""

from __future__ import annotations

import itertools
import logging
import threading
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from pokemon_tcg_client import pokemontcg_image_url

from api.catalog_service import SEED_DB, load_board, row_to_card
from api.demo_mode import demo_mode
from database_clients import reset_request_access_token, set_request_access_token
from services.portfolio_timeseries import portfolio_timeseries

LOG = logging.getLogger("kestrel.api.portfolio")


@contextmanager
def _bind_user_jwt(access_token: str | None) -> Iterator[None]:
    """Bind Bearer in *this* sync thread so RLS client sees Soft Ink JWT."""
    raw = str(access_token or "").strip() or None
    ctx = set_request_access_token(raw)
    try:
        yield
    finally:
        reset_request_access_token(ctx)


def bearer_from_authorization(authorization: str | None) -> str | None:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer":
        return None
    raw = token.strip()
    return raw or None

_LOCK = threading.Lock()
_LOT_SEQ = itertools.count(1)
_WATCH_SEQ = itertools.count(1)
_DEMO_LOTS: dict[str, list[dict[str, Any]]] = {}
_DEMO_WATCH: dict[str, list[dict[str, Any]]] = {}
_SEEDED: set[str] = set()


def _image(card_id: str, existing: str | None = None) -> str | None:
    if existing and str(existing).strip():
        return str(existing).strip()
    return pokemontcg_image_url(str(card_id))


def _seed_demo_user(user_id: str) -> None:
    if user_id in _SEEDED:
        return
    board, _ = load_board()
    picks: list[dict[str, Any]] = []
    if board is not None and not board.empty:
        sample = board.sort_values("price", ascending=False).head(4)
        for _, row in sample.iterrows():
            card = row_to_card(row)
            price = float(card.get("price") or 1.0)
            picks.append(
                {
                    "id": next(_LOT_SEQ),
                    "user_id": user_id,
                    "card_id": card["id"],
                    "quantity": 1 if price > 1.5 else 2,
                    "purchase_price": round(price * 0.92, 4),
                    # Backdate so Soft Ink / Streamlit performance charts have a window.
                    "purchase_date": (date.today() - timedelta(days=75 - len(picks) * 12)).isoformat(),
                    "condition": "NM",
                    "printing": "Normal",
                    "grade": "",
                    "status": "open",
                    "sale_price": None,
                    "sale_date": None,
                    "name": card.get("name"),
                    "rarity": card.get("rarity"),
                    "market_price": price,
                    "image_url": card.get("image_url"),
                }
            )
            if len(picks) >= 3:
                break
    _DEMO_LOTS[user_id] = picks
    watch: list[dict[str, Any]] = []
    if board is not None and not board.empty:
        for _, row in board.sort_values("expected_change_pct", ascending=False).head(5).iterrows():
            card = row_to_card(row)
            if any(p["card_id"] == card["id"] for p in picks):
                continue
            watch.append(
                {
                    "id": next(_WATCH_SEQ),
                    "user_id": user_id,
                    "card_id": card["id"],
                    "created_at": date.today().isoformat(),
                    "name": card.get("name"),
                    "rarity": card.get("rarity"),
                    "market_price": card.get("price"),
                    "image_url": card.get("image_url"),
                }
            )
            if len(watch) >= 3:
                break
    _DEMO_WATCH[user_id] = watch
    _SEEDED.add(user_id)


def _quotes_by_id() -> dict[str, dict[str, Any]]:
    board, _ = load_board()
    if board is None or board.empty:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for _, row in board.iterrows():
        card = row_to_card(row)
        out[str(card["id"])] = card
    return out


def _board_encoding_by_id() -> dict[str, dict[str, Any]]:
    """Raw board rows keyed by card id (includes rarity/supertype encodings)."""
    board, _ = load_board()
    if board is None or board.empty:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for _, row in board.iterrows():
        card_id = str(row.get("id") or row.get("card_id") or "")
        if not card_id:
            continue
        out[card_id] = row.to_dict()
    return out


def _fallback_board_model():
    try:
        from services.model_store import load_model_artifact

        loaded = load_model_artifact()
        if loaded is None:
            return None
        return loaded[0]
    except Exception as exc:
        LOG.info("board model unavailable for portfolio outlook: %s", exc)
        return None


def _attach_lot_outlook(lots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach 30d (preferred) ADD/TRIM/HOLD coach fields; fall back to 7d board model."""
    if not lots:
        return lots
    try:
        import math

        import pandas as pd

        from services.portfolio_outlook import enrich_portfolio_outlook
    except Exception as exc:
        LOG.info("portfolio outlook import failed: %s", exc)
        return lots

    encodings = _board_encoding_by_id()
    rows: list[dict[str, Any]] = []
    for lot in lots:
        card_id = str(lot.get("card_id") or "")
        enc = encodings.get(card_id) or {}
        rows.append(
            {
                **lot,
                "card_id": card_id,
                "quantity": int(lot.get("quantity") or 0),
                "current_price": float(lot.get("current_price") or lot.get("market_price") or 0.0),
                "rarity_encoded": enc.get("rarity_encoded"),
                "supertype_encoded": enc.get("supertype_encoded"),
            }
        )
    frame = pd.DataFrame(rows)
    card_ids = sorted({str(r["card_id"]) for r in rows if r.get("card_id")})
    try:
        history = load_history_for_cards(card_ids)
    except Exception as exc:
        LOG.info("portfolio outlook history load failed: %s", exc)
        history = pd.DataFrame(columns=["card_id", "date", "price"])

    try:
        enriched, info = enrich_portfolio_outlook(
            frame,
            history,
            fallback_model=_fallback_board_model(),
        )
    except Exception as exc:
        LOG.info("enrich_portfolio_outlook failed: %s", exc)
        return lots

    horizon = int(info.get("horizon_days") or 30)

    def _finite(value: Any) -> float | None:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return None
        return num if math.isfinite(num) else None

    out: list[dict[str, Any]] = []
    for row in enriched.to_dict(orient="records"):
        outlook_value = _finite(row.get("outlook_value"))
        payload = {
            **row,
            "outlook_value": outlook_value
            if outlook_value is not None
            else row.get("outlook_value"),
            "outlook_roi_pct": _finite(row.get("outlook_roi_pct")),
            "outlook_lo_pct": _finite(row.get("outlook_lo_pct")),
            "outlook_hi_pct": _finite(row.get("outlook_hi_pct")),
            "outlook_conformal_ok": bool(row.get("outlook_conformal_ok")),
            "lot_action": str(row.get("lot_action") or "HOLD").upper(),
            "is_top_ai": bool(row.get("is_top_ai")),
            "outlook_horizon_days": horizon,
        }
        # Drop helper encodings from API payload.
        payload.pop("rarity_encoded", None)
        payload.pop("supertype_encoded", None)
        payload.pop("outlook_price", None)
        payload.pop("week_price", None)
        payload.pop("week_value", None)
        payload.pop("week_roi_pct", None)
        out.append(payload)
    return out


def enrich_lots(lots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from services.lot_price_adjust import (
        adjust_nm_price,
        lot_price_factor,
        normalize_condition,
        normalize_printing,
    )

    quotes = _quotes_by_id()
    enriched: list[dict[str, Any]] = []
    for lot in lots:
        card_id = str(lot.get("card_id") or "")
        quote = quotes.get(card_id) or {}
        qty = int(lot.get("quantity") or 0)
        cost = float(lot.get("purchase_price") or 0.0)
        condition = normalize_condition(lot.get("condition"))
        printing = normalize_printing(lot.get("printing"))
        factor = lot_price_factor(condition=condition, printing=printing)
        nm_spot = quote.get("price")
        if nm_spot is None:
            nm_spot = lot.get("market_price")
        try:
            nm_spot_f = float(nm_spot) if nm_spot is not None else 0.0
        except (TypeError, ValueError):
            nm_spot_f = 0.0
        spot_f = float(adjust_nm_price(nm_spot_f, condition=condition, printing=printing) or 0.0)
        invested = qty * cost
        market_value = qty * spot_f
        pnl = market_value - invested
        pnl_pct = (pnl / invested * 100.0) if invested > 0 else 0.0
        predicted = quote.get("predicted_price")
        try:
            predicted_nm = float(predicted) if predicted is not None else nm_spot_f
        except (TypeError, ValueError):
            predicted_nm = nm_spot_f
        predicted_f = float(
            adjust_nm_price(predicted_nm, condition=condition, printing=printing) or 0.0
        )
        enriched.append(
            {
                **lot,
                "condition": condition,
                "printing": printing,
                "name": lot.get("name") or quote.get("name"),
                "rarity": lot.get("rarity") or quote.get("rarity"),
                "set_name": quote.get("set_name"),
                "image_url": _image(card_id, lot.get("image_url") or quote.get("image_url")),
                "nm_market_price": nm_spot_f,
                "price_factor": factor,
                "market_price": spot_f,
                "current_price": spot_f,
                "invested": invested,
                "market_value": market_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "signal": quote.get("signal"),
                "expected_change_pct": quote.get("expected_change_pct"),
                "predicted_price": predicted_f,
                "outlook_value": qty * predicted_f,
                "lot_action": "HOLD",
                "outlook_conformal_ok": False,
                "is_top_ai": False,
            }
        )
    return _attach_lot_outlook(enriched)


def enrich_watch(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    quotes = _quotes_by_id()
    out: list[dict[str, Any]] = []
    for row in rows:
        card_id = str(row.get("card_id") or "")
        quote = quotes.get(card_id) or {}
        price = quote.get("price")
        if price is None:
            price = row.get("market_price")
        out.append(
            {
                **row,
                "name": row.get("name") or quote.get("name"),
                "rarity": row.get("rarity") or quote.get("rarity"),
                "set_name": quote.get("set_name"),
                "image_url": _image(card_id, row.get("image_url") or quote.get("image_url")),
                "market_price": float(price) if price is not None else None,
                "signal": quote.get("signal"),
                "expected_change_pct": quote.get("expected_change_pct"),
                "predicted_price": quote.get("predicted_price"),
            }
        )
    return out


def portfolio_summary(lots: list[dict[str, Any]]) -> dict[str, Any]:
    open_lots = [l for l in lots if str(l.get("status") or "open").lower() != "sold"]
    value = float(sum(float(l.get("market_value") or 0.0) for l in open_lots))
    invested = float(sum(float(l.get("invested") or 0.0) for l in open_lots))
    pnl = value - invested
    pnl_pct = (pnl / invested * 100.0) if invested > 0 else 0.0
    outlook = float(sum(float(l.get("outlook_value") or 0.0) for l in open_lots))
    outlook_pct = ((outlook - value) / value * 100.0) if value > 0 else 0.0
    horizons = [
        int(l.get("outlook_horizon_days"))
        for l in open_lots
        if l.get("outlook_horizon_days") is not None
    ]
    horizon = horizons[0] if horizons else 7
    return {
        "lots": len(open_lots),
        "value": value,
        "invested": invested,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "outlook_value": outlook,
        "outlook_pct": outlook_pct,
        "outlook_horizon_days": horizon,
    }


def list_portfolio(
    *,
    user_id: str,
    include_sold: bool = False,
    access_token: str | None = None,
) -> list[dict[str, Any]]:
    if demo_mode():
        with _LOCK:
            _seed_demo_user(user_id)
            lots = list(_DEMO_LOTS.get(user_id) or [])
        if not include_sold:
            lots = [l for l in lots if str(l.get("status") or "open").lower() != "sold"]
        return enrich_lots(lots)

    from database_user import load_portfolio_lots

    with _bind_user_jwt(access_token):
        frame = load_portfolio_lots(user_id=user_id, include_sold=include_sold)
    if frame is None or frame.empty:
        return []
    return enrich_lots(frame.to_dict(orient="records"))


def add_lot(
    *,
    user_id: str,
    card_id: str,
    quantity: int,
    purchase_price: float,
    condition: str = "NM",
    printing: str = "Normal",
    grade: str | None = None,
    purchase_date: str | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    from services.lot_price_adjust import normalize_condition, normalize_printing

    if int(quantity) < 1:
        raise ValueError("Quantity must be at least 1.")
    if float(purchase_price) <= 0:
        raise ValueError("Purchase price must be greater than zero.")
    card_id = str(card_id).strip()
    quotes = _quotes_by_id()
    quote = quotes.get(card_id) or {}
    payload = {
        "user_id": user_id,
        "card_id": card_id,
        "quantity": int(quantity),
        "purchase_price": float(purchase_price),
        "purchase_date": purchase_date or date.today().isoformat(),
        "condition": normalize_condition(condition),
        "printing": normalize_printing(printing),
        "grade": (grade or "").strip(),
        "status": "open",
        "sale_price": None,
        "sale_date": None,
        "name": quote.get("name"),
        "rarity": quote.get("rarity"),
        "market_price": quote.get("price"),
        "image_url": quote.get("image_url") or _image(card_id),
    }
    if demo_mode():
        with _LOCK:
            _seed_demo_user(user_id)
            payload["id"] = next(_LOT_SEQ)
            _DEMO_LOTS.setdefault(user_id, []).append(payload)
        return enrich_lots([payload])[0]

    from database_user import add_portfolio_position, load_portfolio_lots

    with _bind_user_jwt(access_token):
        add_portfolio_position(
            card_id,
            int(quantity),
            float(purchase_price),
            user_id=user_id,
            purchase_date=payload["purchase_date"],
            condition=payload["condition"],
            printing=payload["printing"],
            grade=payload["grade"] or None,
        )
        frame = load_portfolio_lots(user_id=user_id, include_sold=True)
    if frame is None or frame.empty:
        return enrich_lots([payload])[0]
    hit = frame[frame["card_id"].astype(str) == card_id].tail(1)
    if hit.empty:
        return enrich_lots([payload])[0]
    return enrich_lots(hit.to_dict(orient="records"))[0]


def delete_lot(*, user_id: str, entry_id: int, access_token: str | None = None) -> bool:
    if demo_mode():
        with _LOCK:
            lots = _DEMO_LOTS.get(user_id) or []
            keep = [l for l in lots if int(l.get("id") or 0) != int(entry_id)]
            removed = len(keep) != len(lots)
            _DEMO_LOTS[user_id] = keep
            return removed
    from database_user import delete_portfolio_position

    with _bind_user_jwt(access_token):
        return bool(delete_portfolio_position(int(entry_id), user_id=user_id))


def _find_demo_lot(user_id: str, entry_id: int) -> dict[str, Any] | None:
    for lot in _DEMO_LOTS.get(user_id) or []:
        if int(lot.get("id") or 0) == int(entry_id):
            return lot
    return None


def update_lot(
    *,
    user_id: str,
    entry_id: int,
    quantity: int | None = None,
    purchase_price: float | None = None,
    condition: str | None = None,
    printing: str | None = None,
    grade: str | None = None,
    purchase_date: str | None = None,
    access_token: str | None = None,
) -> dict[str, Any] | None:
    from services.lot_price_adjust import normalize_condition, normalize_printing

    if demo_mode():
        with _LOCK:
            _seed_demo_user(user_id)
            lot = _find_demo_lot(user_id, entry_id)
            if lot is None:
                return None
            if str(lot.get("status") or "open").lower() == "sold":
                raise ValueError("Sold lots cannot be edited.")
            if quantity is not None:
                if int(quantity) < 1:
                    raise ValueError("Quantity must be at least 1.")
                lot["quantity"] = int(quantity)
            if purchase_price is not None:
                if float(purchase_price) <= 0:
                    raise ValueError("Purchase price must be greater than zero.")
                lot["purchase_price"] = float(purchase_price)
            if condition is not None:
                lot["condition"] = normalize_condition(condition)
            if printing is not None:
                lot["printing"] = normalize_printing(printing)
            if grade is not None:
                lot["grade"] = (grade or "").strip()
            if purchase_date is not None:
                lot["purchase_date"] = str(purchase_date)
            return enrich_lots([dict(lot)])[0]

    from database_user import load_portfolio_lots, update_portfolio_position

    with _bind_user_jwt(access_token):
        ok = update_portfolio_position(
            int(entry_id),
            user_id=user_id,
            quantity=quantity,
            purchase_price=purchase_price,
            condition=condition,
            printing=printing,
            grade=grade,
            purchase_date=purchase_date,
        )
        if not ok:
            return None
        frame = load_portfolio_lots(user_id=user_id, include_sold=True)
    if frame is None or frame.empty:
        return None
    hit = frame[frame["id"].astype(int) == int(entry_id)]
    if hit.empty:
        return None
    return enrich_lots(hit.to_dict(orient="records"))[0]


def sell_lot(
    *,
    user_id: str,
    entry_id: int,
    sale_price: float,
    sale_date: str | None = None,
    access_token: str | None = None,
) -> dict[str, Any] | None:
    if float(sale_price) <= 0:
        raise ValueError("Sale price must be greater than zero.")
    sold_on = sale_date or date.today().isoformat()
    if demo_mode():
        with _LOCK:
            _seed_demo_user(user_id)
            lot = _find_demo_lot(user_id, entry_id)
            if lot is None:
                return None
            if str(lot.get("status") or "open").lower() == "sold":
                raise ValueError("Lot already sold.")
            lot["status"] = "sold"
            lot["sale_price"] = float(sale_price)
            lot["sale_date"] = sold_on
            return enrich_lots([dict(lot)])[0]

    from database_user import load_portfolio_lots, sell_portfolio_position

    with _bind_user_jwt(access_token):
        ok = sell_portfolio_position(
            int(entry_id),
            user_id=user_id,
            sale_price=float(sale_price),
            sale_date=sold_on,
        )
        if not ok:
            return None
        frame = load_portfolio_lots(user_id=user_id, include_sold=True)
    if frame is None or frame.empty:
        return None
    hit = frame[frame["id"].astype(int) == int(entry_id)]
    if hit.empty:
        return None
    return enrich_lots(hit.to_dict(orient="records"))[0]


def list_watchlist(*, user_id: str, access_token: str | None = None) -> list[dict[str, Any]]:
    if demo_mode():
        with _LOCK:
            _seed_demo_user(user_id)
            rows = list(_DEMO_WATCH.get(user_id) or [])
        return enrich_watch(rows)

    from database_user import load_watchlist

    with _bind_user_jwt(access_token):
        frame = load_watchlist(user_id=user_id)
    if frame is None or frame.empty:
        return []
    return enrich_watch(frame.to_dict(orient="records"))


def add_watch(*, user_id: str, card_id: str, access_token: str | None = None) -> dict[str, Any]:
    card_id = str(card_id).strip()
    if not card_id:
        raise ValueError("card_id required")
    quotes = _quotes_by_id()
    quote = quotes.get(card_id) or {}
    row = {
        "user_id": user_id,
        "card_id": card_id,
        "created_at": date.today().isoformat(),
        "name": quote.get("name"),
        "rarity": quote.get("rarity"),
        "market_price": quote.get("price"),
        "image_url": quote.get("image_url") or _image(card_id),
    }
    if demo_mode():
        with _LOCK:
            _seed_demo_user(user_id)
            existing = _DEMO_WATCH.setdefault(user_id, [])
            for item in existing:
                if str(item.get("card_id")) == card_id:
                    return enrich_watch([item])[0]
            row["id"] = next(_WATCH_SEQ)
            existing.append(row)
        return enrich_watch([row])[0]

    from database_user import add_watchlist_card, load_watchlist

    with _bind_user_jwt(access_token):
        add_watchlist_card(card_id, user_id=user_id)
        frame = load_watchlist(user_id=user_id)
    hit = frame[frame["card_id"].astype(str) == card_id] if frame is not None and not frame.empty else None
    if hit is None or hit.empty:
        return enrich_watch([row])[0]
    return enrich_watch(hit.to_dict(orient="records"))[0]


def remove_watch(*, user_id: str, card_id: str, access_token: str | None = None) -> bool:
    card_id = str(card_id).strip()
    if demo_mode():
        with _LOCK:
            rows = _DEMO_WATCH.get(user_id) or []
            keep = [r for r in rows if str(r.get("card_id")) != card_id]
            removed = len(keep) != len(rows)
            _DEMO_WATCH[user_id] = keep
            return removed
    from database_user import remove_watchlist_card

    with _bind_user_jwt(access_token):
        return bool(remove_watchlist_card(card_id, user_id=user_id))


def is_watched(*, user_id: str, card_id: str, access_token: str | None = None) -> bool:
    card_id = str(card_id).strip()
    if demo_mode():
        with _LOCK:
            _seed_demo_user(user_id)
            return any(str(r.get("card_id")) == card_id for r in (_DEMO_WATCH.get(user_id) or []))
    from database_user import is_on_watchlist

    with _bind_user_jwt(access_token):
        return bool(is_on_watchlist(card_id, user_id=user_id))


def _history_from_seed(card_ids: list[str]) -> pd.DataFrame:
    empty = pd.DataFrame(columns=["card_id", "date", "price"])
    if not card_ids or not Path(SEED_DB).is_file():
        return empty
    try:
        import sqlite3

        placeholders = ",".join("?" for _ in card_ids)
        with sqlite3.connect(SEED_DB) as conn:
            frame = pd.read_sql_query(
                f"SELECT card_id, date, price FROM price_history "
                f"WHERE card_id IN ({placeholders}) ORDER BY date",
                conn,
                params=card_ids,
            )
        return frame if frame is not None and not frame.empty else empty
    except Exception as exc:
        LOG.info("seed history load failed: %s", exc)
        return empty


def load_history_for_cards(card_ids: list[str]) -> pd.DataFrame:
    """Price history for portfolio card ids (Supabase, then seed SQLite)."""
    ids = [str(c).strip() for c in card_ids if str(c).strip()]
    empty = pd.DataFrame(columns=["card_id", "date", "price"])
    if not ids:
        return empty
    try:
        from database_catalog import load_history_frame

        hist = load_history_frame(card_ids=ids)
        if hist is not None and not hist.empty:
            cols = [c for c in ("card_id", "date", "price") if c in hist.columns]
            return hist[cols].copy()
    except Exception as exc:
        LOG.info("supabase history for portfolio failed: %s", exc)
    return _history_from_seed(ids)


def _ai_fair_band(open_lots: list[dict[str, Any]]) -> dict[str, float | None]:
    """Today's model fair total + optional conformal band from open lots."""
    if not open_lots:
        return {"ai_fair_value": None, "ai_lo": None, "ai_hi": None}
    fair = 0.0
    lo = 0.0
    hi = 0.0
    has_band = False
    for lot in open_lots:
        try:
            outlook = float(lot.get("outlook_value") or 0.0)
        except (TypeError, ValueError):
            outlook = 0.0
        fair += outlook
        spot = lot.get("market_price")
        qty = lot.get("quantity") or 1
        try:
            spot_f = float(spot) if spot is not None else None
            qty_f = float(qty)
        except (TypeError, ValueError):
            spot_f = None
            qty_f = 1.0
        lo_pct = lot.get("outlook_lo_pct")
        hi_pct = lot.get("outlook_hi_pct")
        if spot_f is not None and lo_pct is not None and hi_pct is not None:
            try:
                lo += qty_f * spot_f * (1.0 + float(lo_pct) / 100.0)
                hi += qty_f * spot_f * (1.0 + float(hi_pct) / 100.0)
                has_band = True
            except (TypeError, ValueError):
                pass
    return {
        "ai_fair_value": round(fair, 4) if fair else None,
        "ai_lo": round(lo, 4) if has_band else None,
        "ai_hi": round(hi, 4) if has_band else None,
    }


def _drawdown_callouts(
    points: list[dict[str, Any]],
    *,
    open_lots: list[dict[str, Any]],
    min_drawdown_pct: float = 8.0,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Largest peak→trough drawdowns on the MTM curve + TRIM hint."""
    if len(points) < 2:
        return []
    trim_count = sum(
        1
        for lot in open_lots
        if str(lot.get("lot_action") or "").upper() == "TRIM"
        and bool(lot.get("outlook_conformal_ok"))
    )
    peak_val = float(points[0]["market_value"] or 0.0)
    peak_date = str(points[0]["date"])
    candidates: list[dict[str, Any]] = []
    for row in points[1:]:
        value = float(row["market_value"] or 0.0)
        date = str(row["date"])
        if value >= peak_val:
            peak_val = value
            peak_date = date
            continue
        if peak_val <= 0:
            continue
        dd = (peak_val - value) / peak_val * 100.0
        if dd < float(min_drawdown_pct):
            continue
        note = (
            f"MTM drew down {dd:.1f}% from peak. "
            f"{trim_count} open lot(s) currently carry conformal TRIM."
            if trim_count
            else f"MTM drew down {dd:.1f}% from peak."
        )
        candidates.append(
            {
                "peak_date": peak_date,
                "trough_date": date,
                "drawdown_pct": round(dd, 2),
                "peak_value": round(peak_val, 4),
                "trough_value": round(value, 4),
                "trim_count": int(trim_count),
                "note": note,
            }
        )
    # Keep deepest unique troughs.
    candidates.sort(key=lambda r: float(r["drawdown_pct"]), reverse=True)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in candidates:
        key = str(row["trough_date"])
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
        if len(out) >= limit:
            break
    return out


def portfolio_performance(
    *,
    user_id: str,
    max_days: int = 120,
    access_token: str | None = None,
) -> dict[str, Any]:
    """Daily invested cost vs mark-to-market for the user's lots (+ AI overlay)."""
    max_days = max(14, min(int(max_days or 120), 365))
    lots = list_portfolio(user_id=user_id, include_sold=True, access_token=access_token)
    empty = {
        "points": [],
        "days": 0,
        "demo": demo_mode(),
        "ai_fair_value": None,
        "ai_lo": None,
        "ai_hi": None,
        "drawdown_callouts": [],
    }
    if not lots:
        return empty

    lots_frame = pd.DataFrame(lots)
    card_ids = sorted({str(r.get("card_id")) for r in lots if r.get("card_id")})
    history = load_history_for_cards(card_ids)
    series = portfolio_timeseries(lots_frame, history, max_days=max_days)
    points: list[dict[str, Any]] = []
    if series is not None and not series.empty:
        for row in series.itertuples(index=False):
            day = row.date
            date_str = day.strftime("%Y-%m-%d") if hasattr(day, "strftime") else str(day)[:10]
            points.append(
                {
                    "date": date_str,
                    "invested": round(float(row.invested), 4),
                    "market_value": round(float(row.market_value), 4),
                    "ai_fair_value": None,
                    "ai_lo": None,
                    "ai_hi": None,
                }
            )

    open_lots = [l for l in lots if str(l.get("status") or "open").lower() != "sold"]
    band = _ai_fair_band(open_lots)
    if points and band.get("ai_fair_value") is not None:
        points[-1] = {
            **points[-1],
            "ai_fair_value": band["ai_fair_value"],
            "ai_lo": band["ai_lo"],
            "ai_hi": band["ai_hi"],
        }

    callouts = _drawdown_callouts(points, open_lots=open_lots)
    return {
        "points": points,
        "days": len(points),
        "demo": demo_mode(),
        "ai_fair_value": band.get("ai_fair_value"),
        "ai_lo": band.get("ai_lo"),
        "ai_hi": band.get("ai_hi"),
        "drawdown_callouts": callouts,
    }

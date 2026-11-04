"""Portfolio + watchlist service (JWT Supabase or in-memory demo)."""

from __future__ import annotations

import itertools
import logging
import threading
from contextlib import contextmanager
from datetime import date
from typing import Any, Iterator

from pokemon_tcg_client import pokemontcg_image_url

from api.catalog_service import load_board, row_to_card
from api.demo_mode import demo_mode
from database_clients import reset_request_access_token, set_request_access_token

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
                    "purchase_date": date.today().isoformat(),
                    "condition": "NM",
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


def enrich_lots(lots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    quotes = _quotes_by_id()
    enriched: list[dict[str, Any]] = []
    for lot in lots:
        card_id = str(lot.get("card_id") or "")
        quote = quotes.get(card_id) or {}
        qty = int(lot.get("quantity") or 0)
        cost = float(lot.get("purchase_price") or 0.0)
        spot = quote.get("price")
        if spot is None:
            spot = lot.get("market_price")
        try:
            spot_f = float(spot) if spot is not None else 0.0
        except (TypeError, ValueError):
            spot_f = 0.0
        invested = qty * cost
        market_value = qty * spot_f
        pnl = market_value - invested
        pnl_pct = (pnl / invested * 100.0) if invested > 0 else 0.0
        predicted = quote.get("predicted_price")
        try:
            predicted_f = float(predicted) if predicted is not None else spot_f
        except (TypeError, ValueError):
            predicted_f = spot_f
        enriched.append(
            {
                **lot,
                "name": lot.get("name") or quote.get("name"),
                "rarity": lot.get("rarity") or quote.get("rarity"),
                "set_name": quote.get("set_name"),
                "image_url": _image(card_id, lot.get("image_url") or quote.get("image_url")),
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
            }
        )
    return enriched


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
    return {
        "lots": len(open_lots),
        "value": value,
        "invested": invested,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "outlook_value": outlook,
        "outlook_pct": outlook_pct,
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
    grade: str | None = None,
    purchase_date: str | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
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
        "condition": (condition or "NM").strip() or "NM",
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
    grade: str | None = None,
    purchase_date: str | None = None,
    access_token: str | None = None,
) -> dict[str, Any] | None:
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
                lot["condition"] = (condition or "NM").strip() or "NM"
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

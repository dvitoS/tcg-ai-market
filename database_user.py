"""Portfolio / watchlist helpers (JWT / RLS user client)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from database_clients import PAGE, _user_data_client

def load_portfolio_lots(*, user_id: str, include_sold: bool = True) -> pd.DataFrame:
    """Load portfolio lots for one authenticated user only."""
    uid = str(user_id or "").strip()
    empty_cols = [
        "id",
        "user_id",
        "card_id",
        "quantity",
        "purchase_price",
        "purchase_date",
        "condition",
        "grade",
        "status",
        "sale_price",
        "sale_date",
        "name",
        "rarity",
        "market_price",
        "image_url",
    ]
    if not uid:
        return pd.DataFrame(columns=empty_cols)

    client = _user_data_client()
    rows: list[dict[str, Any]] = []
    start = 0
    columns = (
        "id,user_id,card_id,quantity,purchase_price,purchase_date,"
        "condition,grade,status,sale_price,sale_date,"
        "cards(name,rarity,market_price,image_url)"
    )
    while True:
        query = (
            client.table("portfolio")
            .select(columns)
            .eq("user_id", uid)
            .order("id")
            .range(start, start + PAGE - 1)
        )
        try:
            response = query.execute()
        except Exception:
            # Older schema without condition/status columns.
            columns = (
                "id,user_id,card_id,quantity,purchase_price,purchase_date,"
                "cards(name,rarity,market_price,image_url)"
            )
            response = (
                client.table("portfolio")
                .select(columns)
                .eq("user_id", uid)
                .order("id")
                .range(start, start + PAGE - 1)
                .execute()
            )
        batch = list(response.data or [])
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        start += PAGE

    flat: list[dict[str, Any]] = []
    for row in rows:
        card = row.get("cards") or {}
        status = str(row.get("status") or "open").lower()
        if not include_sold and status == "sold":
            continue
        flat.append(
            {
                "id": row.get("id"),
                "user_id": row.get("user_id"),
                "card_id": row.get("card_id"),
                "quantity": row.get("quantity"),
                "purchase_price": row.get("purchase_price"),
                "purchase_date": row.get("purchase_date"),
                "condition": row.get("condition") or "NM",
                "grade": row.get("grade") or "",
                "status": status,
                "sale_price": row.get("sale_price"),
                "sale_date": row.get("sale_date"),
                "name": card.get("name"),
                "rarity": card.get("rarity"),
                "market_price": card.get("market_price"),
                "image_url": card.get("image_url"),
            }
        )
    return pd.DataFrame(flat)


def add_portfolio_position(
    card_id: str,
    quantity: int,
    purchase_price: float,
    *,
    user_id: str,
    purchase_date: str | None = None,
    condition: str = "NM",
    grade: str | None = None,
) -> None:
    uid = str(user_id or "").strip()
    if not uid:
        raise ValueError("Sign in required to add portfolio lots.")
    if int(quantity) < 1:
        raise ValueError("Quantity must be at least 1.")
    if float(purchase_price) <= 0:
        raise ValueError("Purchase price must be greater than zero.")
    client = _user_data_client()
    payload: dict[str, Any] = {
        "user_id": uid,
        "card_id": card_id,
        "quantity": int(quantity),
        "purchase_price": float(purchase_price),
        "purchase_date": purchase_date or date.today().isoformat(),
        "condition": (condition or "NM").strip() or "NM",
        "status": "open",
    }
    if grade:
        payload["grade"] = str(grade).strip()
    try:
        client.table("portfolio").insert(payload).execute()
    except Exception:
        # Fallback for DBs that have not run the condition/status migration yet.
        client.table("portfolio").insert(
            {
                "user_id": uid,
                "card_id": card_id,
                "quantity": int(quantity),
                "purchase_price": float(purchase_price),
                "purchase_date": purchase_date or date.today().isoformat(),
            }
        ).execute()


def update_portfolio_position(
    entry_id: int,
    *,
    user_id: str,
    quantity: int | None = None,
    purchase_price: float | None = None,
    purchase_date: str | None = None,
    condition: str | None = None,
    grade: str | None = None,
) -> bool:
    uid = str(user_id or "").strip()
    if not uid:
        return False
    payload: dict[str, Any] = {}
    if quantity is not None:
        if int(quantity) < 1:
            raise ValueError("Quantity must be at least 1.")
        payload["quantity"] = int(quantity)
    if purchase_price is not None:
        if float(purchase_price) <= 0:
            raise ValueError("Purchase price must be greater than zero.")
        payload["purchase_price"] = float(purchase_price)
    if purchase_date is not None:
        payload["purchase_date"] = str(purchase_date)
    if condition is not None:
        payload["condition"] = str(condition).strip() or "NM"
    if grade is not None:
        payload["grade"] = str(grade).strip()
    if not payload:
        return False
    client = _user_data_client()
    response = (
        client.table("portfolio")
        .update(payload)
        .eq("id", int(entry_id))
        .eq("user_id", uid)
        .execute()
    )
    return bool(response.data)


def sell_portfolio_position(
    entry_id: int,
    *,
    user_id: str,
    sale_price: float,
    sale_date: str | None = None,
) -> bool:
    uid = str(user_id or "").strip()
    if not uid:
        return False
    if float(sale_price) <= 0:
        raise ValueError("Sale price must be greater than zero.")
    client = _user_data_client()
    response = (
        client.table("portfolio")
        .update(
            {
                "status": "sold",
                "sale_price": float(sale_price),
                "sale_date": sale_date or date.today().isoformat(),
            }
        )
        .eq("id", int(entry_id))
        .eq("user_id", uid)
        .execute()
    )
    return bool(response.data)


def delete_portfolio_position(entry_id: int, *, user_id: str) -> bool:
    """Delete only if the lot belongs to this user."""
    uid = str(user_id or "").strip()
    if not uid:
        return False
    client = _user_data_client()
    response = (
        client.table("portfolio")
        .delete()
        .eq("id", int(entry_id))
        .eq("user_id", uid)
        .execute()
    )
    return bool(response.data)


def load_watchlist(*, user_id: str) -> pd.DataFrame:
    uid = str(user_id or "").strip()
    empty = pd.DataFrame(
        columns=["id", "user_id", "card_id", "created_at", "name", "rarity", "market_price", "image_url"]
    )
    if not uid:
        return empty
    client = _user_data_client()
    try:
        response = (
            client.table("watchlist")
            .select("id,user_id,card_id,created_at,cards(name,rarity,market_price,image_url)")
            .eq("user_id", uid)
            .order("id", desc=True)
            .execute()
        )
    except Exception:
        return empty
    flat: list[dict[str, Any]] = []
    for row in list(response.data or []):
        card = row.get("cards") or {}
        flat.append(
            {
                "id": row.get("id"),
                "user_id": row.get("user_id"),
                "card_id": row.get("card_id"),
                "created_at": row.get("created_at"),
                "name": card.get("name"),
                "rarity": card.get("rarity"),
                "market_price": card.get("market_price"),
                "image_url": card.get("image_url"),
            }
        )
    return pd.DataFrame(flat)


def add_watchlist_card(card_id: str, *, user_id: str) -> None:
    uid = str(user_id or "").strip()
    if not uid:
        raise ValueError("Sign in required for watchlist.")
    client = _user_data_client()
    client.table("watchlist").upsert(
        {"user_id": uid, "card_id": str(card_id)},
        on_conflict="user_id,card_id",
    ).execute()


def remove_watchlist_card(card_id: str, *, user_id: str) -> bool:
    uid = str(user_id or "").strip()
    if not uid:
        return False
    client = _user_data_client()
    response = (
        client.table("watchlist")
        .delete()
        .eq("user_id", uid)
        .eq("card_id", str(card_id))
        .execute()
    )
    return bool(response.data)


def is_on_watchlist(card_id: str, *, user_id: str) -> bool:
    uid = str(user_id or "").strip()
    if not uid:
        return False
    try:
        client = _user_data_client()
        response = (
            client.table("watchlist")
            .select("id")
            .eq("user_id", uid)
            .eq("card_id", str(card_id))
            .limit(1)
            .execute()
        )
    except Exception:
        return False
    return bool(response.data)


def ensure_portfolio_user_id_column() -> None:
    """Best-effort DDL when SUPABASE_DB_URL is set (existing projects)."""
    from config import _secret

    db_url = (_secret("SUPABASE_DB_URL") or "").strip()
    if not db_url:
        return
    try:
        import psycopg
        from psycopg import ClientCursor
    except ImportError:
        return
    ddl = """
    alter table public.portfolio
      add column if not exists user_id uuid references auth.users (id) on delete cascade;
    create index if not exists portfolio_user_id_idx on public.portfolio (user_id);
    notify pgrst, 'reload schema';
    """
    with psycopg.connect(db_url, autocommit=True, cursor_factory=ClientCursor) as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)


def load_all_watchlists() -> pd.DataFrame:
    """Service-role dump of all watchlist rows (nightly email digests)."""
    from database_clients import fetch_all

    try:
        rows = fetch_all(
            "watchlist",
            "id,user_id,card_id,created_at,cards(name,rarity,market_price,image_url)",
            order="user_id",
        )
    except Exception:
        return pd.DataFrame(
            columns=[
                "id",
                "user_id",
                "card_id",
                "created_at",
                "name",
                "rarity",
                "market_price",
                "image_url",
            ]
        )
    flat: list[dict[str, Any]] = []
    for row in rows:
        card = row.get("cards") or {}
        flat.append(
            {
                "id": row.get("id"),
                "user_id": row.get("user_id"),
                "card_id": row.get("card_id"),
                "created_at": row.get("created_at"),
                "name": card.get("name"),
                "rarity": card.get("rarity"),
                "market_price": card.get("market_price"),
                "image_url": card.get("image_url"),
            }
        )
    return pd.DataFrame(flat)

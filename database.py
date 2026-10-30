"""Supabase (PostgreSQL) sloj — zamjena za lokalni SQLite/SQLAlchemy."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from config import SEED_DATABASE_PATH, _secret, get_supabase_credentials

if TYPE_CHECKING:
    from supabase import Client


def _supabase_api():
    """Lazy import — keeps module load working if supabase wheels are mid-install."""
    try:
        from supabase import Client, create_client
    except ImportError as exc:
        raise ImportError(
            "supabase package missing or broken. "
            "Add 'supabase' to requirements.txt and reboot the Cloud app."
        ) from exc
    return Client, create_client

PAGE = 1000

SCHEMA_SQL = (Path(__file__).resolve().parent / "supabase_schema.sql").read_text(encoding="utf-8")

# PostgREST schema cache: None = još nije provjereno.
_TCGPLAYER_ID_COLUMN: bool | None = None

TCGPLAYER_ID_MIGRATE_SQL = (
    "alter table public.cards add column if not exists tcgplayer_id text;\n"
    "notify pgrst, 'reload schema';"
)


@dataclass
class Card:
    id: str
    name: str | None = None
    supertype: str | None = None
    rarity: str | None = None
    set_name: str | None = None
    market_price: float | None = None
    pokewallet_id: str | None = None
    tcgplayer_id: str | None = None
    image_url: str | None = None


def _require_supabase_env() -> tuple[str, str]:
    url, key = get_supabase_credentials()
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY are not set. "
            "Add them in Streamlit Secrets (Cloud) or .env (local)."
        )
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        raise RuntimeError(
            "SUPABASE_URL must be the Project URL (https://xxxx.supabase.co), "
            "not a Postgres connection string. Put the Postgres URI in SUPABASE_DB_URL."
        )
    if "supabase.co" not in url and "localhost" not in url:
        raise RuntimeError(
            f"Suspicious SUPABASE_URL: {url!r}. "
            "Expected e.g. https://YOUR_PROJECT.supabase.co "
            "(without /rest/v1 at the end)."
        )
    return url, key


@lru_cache(maxsize=1)
def get_supabase():
    """Service-role (or configured key) client — catalog/history/sync."""
    _, create_client = _supabase_api()
    url, key = _require_supabase_env()
    return create_client(url, key)


def get_user_supabase():
    """Authed anon client with the signed-in user's JWT (portfolio/watchlist RLS).

    Returns None when anon key or session tokens are missing — callers fall back
    to get_supabase() + explicit user_id filters.
    """
    try:
        import streamlit as st

        from auth import SESSION_ACCESS_KEY, SESSION_REFRESH_KEY, refresh_session
        from config import _clean_secret_value, get_supabase_auth_credentials
    except Exception:
        return None

    url, anon = get_supabase_auth_credentials()
    # Prefer true anon key for RLS; if only service role is configured, skip.
    has_anon = bool(_clean_secret_value(_secret("SUPABASE_ANON_KEY")))
    if not url or not anon or not has_anon:
        return None
    refresh_session()
    access = str(st.session_state.get(SESSION_ACCESS_KEY) or "").strip()
    refresh = str(st.session_state.get(SESSION_REFRESH_KEY) or "").strip()
    if not access:
        return None
    try:
        _, create_client = _supabase_api()
        client = create_client(url, anon)
        # refresh_token is required by gotrue set_session
        client.auth.set_session(access, refresh or access)
        # Touch auth so a bad token fails here instead of later on PostgREST.
        client.auth.get_user(access)
        return client
    except Exception as exc:
        import logging

        logging.getLogger("tcg.database").warning("get_user_supabase failed: %s", exc)
        return None


def _user_or_service_client():
    return get_user_supabase() or get_supabase()


def user_data_client_mode() -> str:
    """How portfolio/watchlist will be queried: jwt | missing_anon | missing_token | service_fallback | anonymous."""
    try:
        import auth as auth_mod
        from config import _clean_secret_value
    except Exception:
        return "anonymous"
    if not auth_mod.is_authenticated():
        return "anonymous"
    has_anon = bool(_clean_secret_value(_secret("SUPABASE_ANON_KEY")))
    if not has_anon:
        return "missing_anon"
    if not auth_mod.has_jwt_tokens():
        return "missing_token"
    if get_user_supabase() is not None:
        return "jwt"
    return "service_fallback"


def _chunked(rows: list[dict[str, Any]], size: int = 500):
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _as_iso_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _card_from_row(row: dict[str, Any]) -> Card:
    price = row.get("market_price")
    return Card(
        id=str(row["id"]),
        name=row.get("name"),
        supertype=row.get("supertype"),
        rarity=row.get("rarity"),
        set_name=row.get("set_name"),
        market_price=float(price) if price is not None else None,
        pokewallet_id=row.get("pokewallet_id"),
        tcgplayer_id=row.get("tcgplayer_id"),
        image_url=row.get("image_url"),
    )


def fetch_all(table: str, columns: str = "*", *, order: str | None = None) -> list[dict[str, Any]]:
    """Straničenje — PostgREST default max ~1000 redova po zahtjevu."""
    client = get_supabase()
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        query = client.table(table).select(columns)
        if order:
            query = query.order(order)
        response = query.range(start, start + PAGE - 1).execute()
        batch = list(response.data or [])
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        start += PAGE
    return rows


def table_count(table: str) -> int:
    client = get_supabase()
    response = client.table(table).select("*", count="exact").limit(1).execute()
    return int(response.count or 0)


def _apply_schema_via_postgres(db_url: str) -> None:
    """CREATE TABLE IF NOT EXISTS preko direktnog Postgres URI-ja (opcionalno)."""
    try:
        import psycopg
        from psycopg import ClientCursor
    except ImportError as exc:
        raise RuntimeError(
            "For automatic DDL install psycopg: pip install 'psycopg[binary]'"
        ) from exc
    # ClientCursor podržava više SQL naredbi u jednom execute().
    with psycopg.connect(db_url, autocommit=True, cursor_factory=ClientCursor) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)


def _verify_tables(client: Any) -> None:
    missing: list[str] = []
    details: list[str] = []
    for name in ("cards", "price_history", "portfolio"):
        try:
            client.table(name).select("*").limit(1).execute()
        except Exception as exc:
            missing.append(name)
            details.append(f"{name}: {exc}")
    if missing:
        detail = " | ".join(details)
        raise RuntimeError(
            "Supabase tables are missing or not visible to the API: "
            + ", ".join(missing)
            + ". Run supabase_schema.sql in the SQL Editor (whole file → Run), "
            "then Reload schema cache. Detail: "
            + detail
        )


def _backfill_image_urls() -> None:
    client = get_supabase()
    rows = fetch_all("cards", "id,image_url")
    updates: list[dict[str, Any]] = []
    for row in rows:
        if row.get("image_url"):
            continue
        card_id = str(row["id"])
        if "-" not in card_id:
            continue
        set_code, number = card_id.rsplit("-", 1)
        updates.append(
            {
                "id": card_id,
                "image_url": f"https://images.pokemontcg.io/{set_code}/{number}.png",
            }
        )
    for batch in _chunked(updates):
        client.table("cards").upsert(batch, on_conflict="id").execute()


def init_db() -> None:
    """Inicijalizacija: opcionalni DDL + provjera tablica + backfill image_url."""
    client = get_supabase()
    db_url = _secret("SUPABASE_DB_URL")
    if db_url:
        _apply_schema_via_postgres(db_url)
    _verify_tables(client)
    _backfill_image_urls()


def ensure_seed_database() -> bool:
    """Ako je price_history prazna, uvezi lokalni SQLite seed u Supabase."""
    init_db()
    if table_count("price_history") > 0:
        return False
    if not SEED_DATABASE_PATH.is_file():
        return False

    with sqlite3.connect(SEED_DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cards = [dict(row) for row in conn.execute("SELECT * FROM cards")]
        history = [dict(row) for row in conn.execute(
            "SELECT card_id, price, date FROM price_history"
        )]

    if not cards:
        return False

    client = get_supabase()
    card_rows = []
    for row in cards:
        card_rows.append(
            {
                "id": row["id"],
                "name": row["name"],
                "supertype": row["supertype"],
                "rarity": row["rarity"],
                "set_name": row["set_name"],
                "market_price": row["market_price"],
                "pokewallet_id": row["pokewallet_id"] if "pokewallet_id" in row.keys() else None,
                "image_url": row["image_url"] if "image_url" in row.keys() else None,
            }
        )
    for batch in _chunked(card_rows):
        client.table("cards").upsert(batch, on_conflict="id").execute()

    history_rows = [
        {
            "card_id": row["card_id"],
            "price": float(row["price"]),
            "date": _as_iso_date(row["date"]),
        }
        for row in history
    ]
    for batch in _chunked(history_rows):
        client.table("price_history").insert(batch).execute()

    return table_count("price_history") > 0


def list_cards(*, limit: int | None = None, order_price_desc: bool = False) -> list[Card]:
    rows = fetch_all("cards", "*")
    cards = [_card_from_row(row) for row in rows]
    if order_price_desc:
        cards.sort(key=lambda c: (c.market_price is not None, c.market_price or 0.0), reverse=True)
    else:
        cards.sort(key=lambda c: c.id)
    if limit is not None:
        return cards[: int(limit)]
    return cards


def get_card(card_id: str) -> Card | None:
    client = get_supabase()
    response = client.table("cards").select("*").eq("id", card_id).limit(1).execute()
    rows = response.data or []
    return _card_from_row(rows[0]) if rows else None


def cards_have_tcgplayer_id_column(*, force: bool = False) -> bool:
    """True ako PostgREST vidi cards.tcgplayer_id (nakon ALTER + reload cache).

    Positive results stay cached. Missing-column (False) is re-probed so a
    just-applied SQL migration is picked up without restarting Python.
    """
    global _TCGPLAYER_ID_COLUMN
    if not force and _TCGPLAYER_ID_COLUMN is True:
        return True
    client = get_supabase()
    try:
        client.table("cards").select("tcgplayer_id").limit(1).execute()
        _TCGPLAYER_ID_COLUMN = True
    except Exception as exc:
        text = str(exc).lower()
        if "tcgplayer_id" in text or "pgrst204" in text or "42703" in text:
            _TCGPLAYER_ID_COLUMN = False
            print(
                "Note: cards.tcgplayer_id is missing in Supabase.\n"
                "Run in SQL Editor:\n"
                f"{TCGPLAYER_ID_MIGRATE_SQL}"
            )
        else:
            raise
    return bool(_TCGPLAYER_ID_COLUMN)


def upsert_cards(cards: list[dict[str, Any]]) -> int:
    if not cards:
        return 0
    client = get_supabase()
    include_tcp = cards_have_tcgplayer_id_column()
    payload = []
    for card in cards:
        row: dict[str, Any] = {
            "id": card["id"],
            "name": card.get("name"),
            "supertype": card.get("supertype"),
            "rarity": card.get("rarity"),
            "set_name": card.get("set_name"),
            "market_price": card.get("market_price"),
            "pokewallet_id": card.get("pokewallet_id"),
            "image_url": card.get("image_url"),
        }
        if include_tcp and card.get("tcgplayer_id"):
            row["tcgplayer_id"] = card.get("tcgplayer_id")
        payload.append(row)
    for batch in _chunked(payload):
        client.table("cards").upsert(batch, on_conflict="id").execute()
    return len(payload)


def update_card_pokewallet_id(card_id: str, pokewallet_id: str) -> None:
    client = get_supabase()
    client.table("cards").update({"pokewallet_id": pokewallet_id}).eq("id", card_id).execute()


def update_card_market_price(card_id: str, market_price: float, *, tcgplayer_id: str | None = None) -> None:
    client = get_supabase()
    payload: dict[str, Any] = {"market_price": float(market_price)}
    if tcgplayer_id and cards_have_tcgplayer_id_column():
        payload["tcgplayer_id"] = str(tcgplayer_id)
    client.table("cards").update(payload).eq("id", card_id).execute()


def update_card_tcgplayer_id(card_id: str, tcgplayer_id: str) -> None:
    """Spremi TCGplayer product id (za JustTCG live history)."""
    if not tcgplayer_id or not cards_have_tcgplayer_id_column():
        return
    client = get_supabase()
    client.table("cards").update({"tcgplayer_id": str(tcgplayer_id)}).eq("id", card_id).execute()


def replace_card_history(card_id: str, points: list[dict[str, Any]]) -> int:
    if not points:
        return 0
    client = get_supabase()
    client.table("price_history").delete().eq("card_id", card_id).execute()
    rows = [
        {
            "card_id": card_id,
            "price": float(point["price"]),
            "date": _as_iso_date(point["date"]),
        }
        for point in points
    ]
    for batch in _chunked(rows):
        client.table("price_history").insert(batch).execute()
    return len(rows)


def clear_price_history() -> None:
    client = get_supabase()
    # PostgREST delete-all: filter koji uvijek prolazi.
    client.table("price_history").delete().neq("card_id", "").execute()


def insert_price_history(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    client = get_supabase()
    payload = [
        {
            "card_id": row["card_id"],
            "price": float(row["price"]),
            "date": _as_iso_date(row["date"]),
        }
        for row in rows
    ]
    for batch in _chunked(payload):
        client.table("price_history").insert(batch).execute()
    return len(payload)


def distinct_history_card_ids() -> set[str]:
    rows = fetch_all("price_history", "card_id")
    return {str(row["card_id"]) for row in rows}


def load_history_frame() -> pd.DataFrame:
    """price_history ⨝ cards → DataFrame (isti oblik kao stari SQL join)."""
    try:
        rows = fetch_all(
            "price_history",
            "card_id,price,date,cards(name,supertype,rarity,set_name,market_price)",
        )
        flat: list[dict[str, Any]] = []
        for row in rows:
            card = row.get("cards") or {}
            if not card:
                continue
            flat.append(
                {
                    "card_id": row.get("card_id"),
                    "price": row.get("price"),
                    "date": row.get("date"),
                    "name": card.get("name"),
                    "supertype": card.get("supertype"),
                    "rarity": card.get("rarity"),
                    "set_name": card.get("set_name"),
                    "market_price": card.get("market_price"),
                }
            )
        if flat:
            return pd.DataFrame(flat)
    except Exception:
        pass

    # Fallback bez PostgREST embeda: dva upita + merge u Pandasu.
    history = pd.DataFrame(fetch_all("price_history", "card_id,price,date"))
    cards = pd.DataFrame(
        fetch_all("cards", "id,name,supertype,rarity,set_name,market_price")
    )
    if history.empty or cards.empty:
        return pd.DataFrame(
            columns=[
                "card_id",
                "price",
                "date",
                "name",
                "supertype",
                "rarity",
                "set_name",
                "market_price",
            ]
        )
    return history.merge(cards, left_on="card_id", right_on="id", how="inner").drop(
        columns=["id"]
    )


def load_cards_frame() -> pd.DataFrame:
    return pd.DataFrame(fetch_all("cards", "*"))


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

    client = _user_or_service_client()
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
    client = _user_or_service_client()
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
    client = _user_or_service_client()
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
    client = _user_or_service_client()
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
    client = _user_or_service_client()
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
    client = _user_or_service_client()
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
    client = _user_or_service_client()
    client.table("watchlist").upsert(
        {"user_id": uid, "card_id": str(card_id)},
        on_conflict="user_id,card_id",
    ).execute()


def remove_watchlist_card(card_id: str, *, user_id: str) -> bool:
    uid = str(user_id or "").strip()
    if not uid:
        return False
    client = _user_or_service_client()
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
    client = _user_or_service_client()
    try:
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


def cards_summary() -> tuple[int, int, int]:
    cards = fetch_all("cards", "id,market_price")
    total = len(cards)
    with_price = sum(1 for row in cards if row.get("market_price") is not None)
    history_rows = table_count("price_history")
    return total, with_price, history_rows


# Kompatibilnost sa starim importima koji su očekivali ORM session.
def get_session() -> None:
    raise RuntimeError("SQLAlchemy session je uklonjen — koristi supabase helper funkcije iz database.py.")

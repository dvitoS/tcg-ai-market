"""Supabase (PostgreSQL) sloj — zamjena za lokalni SQLite/SQLAlchemy."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from supabase import Client, create_client

from config import SEED_DATABASE_PATH, SUPABASE_DB_URL, SUPABASE_KEY, SUPABASE_URL

PAGE = 1000

SCHEMA_SQL = (Path(__file__).resolve().parent / "supabase_schema.sql").read_text(encoding="utf-8")


@dataclass
class Card:
    id: str
    name: str | None = None
    supertype: str | None = None
    rarity: str | None = None
    set_name: str | None = None
    market_price: float | None = None
    pokewallet_id: str | None = None
    image_url: str | None = None


def _require_supabase_env() -> tuple[str, str]:
    # Ponovno čitaj secrets (Streamlit Cloud ih injektira kasnije od importa).
    from config import _secret

    url = (SUPABASE_URL or _secret("SUPABASE_URL")).strip()
    key = (SUPABASE_KEY or _secret("SUPABASE_KEY")).strip()
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL i SUPABASE_KEY nisu postavljeni. "
            "Dodaj ih u .env (lokalno) ili Streamlit Secrets (Cloud)."
        )
    return url, key


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    url, key = _require_supabase_env()
    return create_client(url, key)


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
    except ImportError as exc:
        raise RuntimeError(
            "Za automatski DDL instaliraj psycopg: pip install 'psycopg[binary]'"
        ) from exc
    with psycopg.connect(db_url) as conn:
        conn.execute(SCHEMA_SQL)
        conn.commit()


def _verify_tables(client: Client) -> None:
    missing: list[str] = []
    for name in ("cards", "price_history", "portfolio"):
        try:
            client.table(name).select("*").limit(1).execute()
        except Exception:
            missing.append(name)
    if missing:
        raise RuntimeError(
            "Supabase tablice nedostaju: "
            + ", ".join(missing)
            + ". Pokreni supabase_schema.sql u SQL Editoru "
            "ili postavi SUPABASE_DB_URL pa ponovno init_db()."
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
    if SUPABASE_DB_URL:
        _apply_schema_via_postgres(SUPABASE_DB_URL)
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


def upsert_cards(cards: list[dict[str, Any]]) -> int:
    if not cards:
        return 0
    client = get_supabase()
    payload = []
    for card in cards:
        payload.append(
            {
                "id": card["id"],
                "name": card.get("name"),
                "supertype": card.get("supertype"),
                "rarity": card.get("rarity"),
                "set_name": card.get("set_name"),
                "market_price": card.get("market_price"),
                "pokewallet_id": card.get("pokewallet_id"),
                "image_url": card.get("image_url"),
            }
        )
    for batch in _chunked(payload):
        client.table("cards").upsert(batch, on_conflict="id").execute()
    return len(payload)


def update_card_pokewallet_id(card_id: str, pokewallet_id: str) -> None:
    client = get_supabase()
    client.table("cards").update({"pokewallet_id": pokewallet_id}).eq("id", card_id).execute()


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


def load_portfolio_lots() -> pd.DataFrame:
    rows = fetch_all(
        "portfolio",
        "id,card_id,quantity,purchase_price,purchase_date,"
        "cards(name,rarity,market_price,image_url)",
        order="id",
    )
    flat: list[dict[str, Any]] = []
    for row in rows:
        card = row.get("cards") or {}
        flat.append(
            {
                "id": row.get("id"),
                "card_id": row.get("card_id"),
                "quantity": row.get("quantity"),
                "purchase_price": row.get("purchase_price"),
                "purchase_date": row.get("purchase_date"),
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
    purchase_date: str | None = None,
) -> None:
    if int(quantity) < 1:
        raise ValueError("Količina mora biti barem 1.")
    if float(purchase_price) <= 0:
        raise ValueError("Nabavna cijena mora biti veća od nule.")
    client = get_supabase()
    client.table("portfolio").insert(
        {
            "card_id": card_id,
            "quantity": int(quantity),
            "purchase_price": float(purchase_price),
            "purchase_date": purchase_date or date.today().isoformat(),
        }
    ).execute()


def delete_portfolio_position(entry_id: int) -> bool:
    client = get_supabase()
    response = client.table("portfolio").delete().eq("id", int(entry_id)).execute()
    return bool(response.data)


def cards_summary() -> tuple[int, int, int]:
    cards = fetch_all("cards", "id,market_price")
    total = len(cards)
    with_price = sum(1 for row in cards if row.get("market_price") is not None)
    history_rows = table_count("price_history")
    return total, with_price, history_rows


# Kompatibilnost sa starim importima koji su očekivali ORM session.
def get_session() -> None:
    raise RuntimeError("SQLAlchemy session je uklonjen — koristi supabase helper funkcije iz database.py.")

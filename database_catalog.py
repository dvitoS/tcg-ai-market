"""Catalog / history Supabase helpers (service_role)."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from config import SEED_DATABASE_PATH, _secret
from database_clients import (
    PAGE,
    Card,
    _as_iso_date,
    _card_from_row,
    _chunked,
    call_with_supabase_reconnect,
    fetch_all,
    get_supabase,
    table_count,
)

LOG = logging.getLogger("tcg.database_catalog")

SCHEMA_SQL = (Path(__file__).resolve().parent / "supabase_schema.sql").read_text(encoding="utf-8")

# PostgREST schema cache: None = još nije provjereno.
_TCGPLAYER_ID_COLUMN: bool | None = None

TCGPLAYER_ID_MIGRATE_SQL = (
    "alter table public.cards add column if not exists tcgplayer_id text;\n"
    "notify pgrst, 'reload schema';"
)

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
    from database_clients import table_has_rows

    init_db()
    # Never exact-COUNT price_history here — 2M+ rows → PostgREST 57014.
    if table_has_rows("price_history"):
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

    from database_clients import table_has_rows

    return table_has_rows("price_history")


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


def card_counts_by_set_id() -> dict[str, int]:
    """Count cards in DB keyed by pokemontcg set id (prefix before last '-')."""
    counts: dict[str, int] = {}
    for card in list_cards(limit=None, order_price_desc=False):
        cid = str(card.id or "")
        if "-" not in cid:
            continue
        set_id = cid.rsplit("-", 1)[0].strip()
        if not set_id:
            continue
        counts[set_id] = counts.get(set_id, 0) + 1
    return counts


def list_cards_for_sync(*, limit: int | None = None) -> list[Card]:
    """Prefer cards missing price_history, then higher market price (smart nightly limits)."""
    cards = list_cards(limit=None, order_price_desc=False)
    if not cards:
        return []
    have = distinct_history_card_ids()
    cards.sort(
        key=lambda c: (
            0 if str(c.id) not in have else 1,
            -(c.market_price or 0.0),
            str(c.id),
        )
    )
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


def clear_card_market_price(card_id: str) -> None:
    """Null ``cards.market_price`` so a later JustTCG heal is not blocked by skip_absurd."""
    clear_card_market_prices([card_id])


def clear_card_market_prices(card_ids: list[str] | set[str]) -> int:
    """Batch-null ``cards.market_price`` for many ids (one PostgREST call per chunk)."""
    ids = sorted({str(cid).strip() for cid in (card_ids or []) if str(cid).strip()})
    if not ids:
        return 0
    client = get_supabase()
    updated = 0
    for chunk in _chunked(ids, size=80):
        client.table("cards").update({"market_price": None}).in_("id", chunk).execute()
        updated += len(chunk)
    return updated


def delete_card_history(card_id: str) -> None:
    """Delete price_history for one card (not a mass wipe)."""
    client = get_supabase()
    client.table("price_history").delete().eq("card_id", card_id).execute()


def update_card_tcgplayer_id(card_id: str, tcgplayer_id: str) -> None:
    """Spremi TCGplayer product id (za JustTCG live history)."""
    if not tcgplayer_id or not cards_have_tcgplayer_id_column():
        return
    client = get_supabase()
    client.table("cards").update({"tcgplayer_id": str(tcgplayer_id)}).eq("id", card_id).execute()


def replace_card_history(card_id: str, points: list[dict[str, Any]]) -> int:
    if not points:
        return 0
    rows = [
        {
            "card_id": card_id,
            "price": float(point["price"]),
            "date": _as_iso_date(point["date"]),
        }
        for point in points
    ]

    def _write() -> int:
        client = get_supabase()
        client.table("price_history").delete().eq("card_id", card_id).execute()
        for batch in _chunked(rows):
            client.table("price_history").insert(batch).execute()
        return len(rows)

    # Nightly history writes can hit a stale HTTP/2 connection mid-card;
    # reconnect + retry instead of failing the whole phase.
    return call_with_supabase_reconnect(
        _write, label=f"replace_card_history:{card_id}"
    )


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


def distinct_history_card_ids_since(since_date: str) -> set[str]:
    """Distinct card_ids with at least one price_history row on/after since_date."""
    client = get_supabase()
    ids: set[str] = set()
    start = 0
    while True:
        response = (
            client.table("price_history")
            .select("card_id")
            .gte("date", since_date)
            .order("card_id")
            .range(start, start + PAGE - 1)
            .execute()
        )
        batch = list(response.data or [])
        for row in batch:
            cid = row.get("card_id")
            if cid is not None:
                ids.add(str(cid))
        if len(batch) < PAGE:
            break
        start += PAGE
    return ids


# Keep each PostgREST ``in_(card_id)`` query small enough that OFFSET pagination
# finishes inside statement_timeout (date-only scans of ~2M rows → 57014).
HISTORY_CARD_CHUNK = 150


def _resolve_history_card_ids(card_ids: list[str] | None) -> list[str]:
    """Explicit ids, or every catalog card id when the caller left the filter open.

    Date-only ``price_history`` scans still hit PostgREST 57014 under deep
    OFFSET even with a ``since_date`` floor — chunking by ``card_id`` keeps each
    query bounded (~150 cards × window days).
    """
    id_list = [str(x) for x in (card_ids or []) if str(x).strip()]
    if id_list:
        return id_list
    rows = fetch_all("cards", "id")
    resolved = [str(row["id"]) for row in rows if row.get("id") is not None]
    if resolved:
        LOG.info(
            "price_history load: auto-chunking by %s catalog card_ids (no card_ids filter)",
            len(resolved),
        )
    return resolved


def _history_id_chunks(card_ids: list[str] | None) -> list[list[str]]:
    """Chunk card ids for PostgREST ``in_`` filters (empty → no queries)."""
    id_list = [str(x) for x in (card_ids or []) if str(x).strip()]
    if not id_list:
        return []
    return [
        id_list[i : i + HISTORY_CARD_CHUNK]
        for i in range(0, len(id_list), HISTORY_CARD_CHUNK)
    ]


def _fetch_price_history_rows(
    *,
    card_ids: list[str] | None = None,
    since_date: str | None = None,
    embed_cards: bool = True,
) -> list[dict[str, Any]]:
    """Paginated price_history rows, scoped to cards (+ optional date floor).

    Never runs an unscoped full-table / date-only scan — those time out (57014)
    once ``price_history`` is multi-million rows. Missing ``card_ids`` resolves
    to the catalog and loads in ``HISTORY_CARD_CHUNK`` batches.
    """
    client = get_supabase()
    columns = (
        "card_id,price,date,cards(name,supertype,rarity,set_name,market_price)"
        if embed_cards
        else "card_id,price,date"
    )
    resolved = _resolve_history_card_ids(card_ids)
    chunks = _history_id_chunks(resolved)
    if not chunks:
        return []

    rows: list[dict[str, Any]] = []
    total_chunks = len(chunks)
    for idx, chunk in enumerate(chunks):
        start = 0
        while True:
            query = (
                client.table("price_history")
                .select(columns)
                .in_("card_id", chunk)
            )
            if since_date:
                query = query.gte("date", since_date)
            response = (
                query.order("card_id").order("date").range(start, start + PAGE - 1).execute()
            )
            batch = list(response.data or [])
            rows.extend(batch)
            if len(batch) < PAGE:
                break
            start += PAGE
        if idx == 0 or (idx + 1) % 25 == 0 or idx + 1 == total_chunks:
            LOG.info(
                "price_history fetch %s/%s chunks rows=%s embed=%s since=%s",
                idx + 1,
                total_chunks,
                len(rows),
                embed_cards,
                since_date,
            )
    return rows


def _history_empty_frame() -> pd.DataFrame:
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


def load_history_frame(
    *,
    card_ids: list[str] | set[str] | None = None,
    since_date: str | None = None,
) -> pd.DataFrame:
    """price_history ⨝ cards → DataFrame (isti oblik kao stari SQL join).

    Prefer a ``since_date`` (and/or card ids). Unscoped / date-only pulls of
    multi-million ``price_history`` rows time out on Supabase (57014); missing
    card ids are expanded to the catalog and fetched in card_id chunks.
    """
    id_list = [str(x) for x in (card_ids or []) if str(x).strip()] or None
    try:
        raw_rows = _fetch_price_history_rows(
            card_ids=id_list, since_date=since_date, embed_cards=True
        )
        flat: list[dict[str, Any]] = []
        for row in raw_rows:
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
    except Exception as exc:
        LOG.warning(
            "price_history embed load failed (falling back without embed): %s",
            exc,
        )

    # Fallback without PostgREST embed — still scoped by card_ids / since_date.
    # Never fetch_all() the whole price_history table (2M+ rows → statement timeout).
    try:
        history = pd.DataFrame(
            _fetch_price_history_rows(
                card_ids=id_list, since_date=since_date, embed_cards=False
            )
        )
    except Exception as exc:
        LOG.error("price_history scoped load failed: %s", exc)
        return _history_empty_frame()
    cards = pd.DataFrame(
        fetch_all("cards", "id,name,supertype,rarity,set_name,market_price")
    )
    if history.empty or cards.empty:
        return _history_empty_frame()
    merged = history.merge(cards, left_on="card_id", right_on="id", how="inner").drop(
        columns=["id"]
    )
    return merged.reset_index(drop=True)


def load_cards_frame() -> pd.DataFrame:
    return pd.DataFrame(fetch_all("cards", "*"))


def cards_summary() -> tuple[int, int, int]:
    cards = fetch_all("cards", "id,market_price")
    total = len(cards)
    with_price = sum(1 for row in cards if row.get("market_price") is not None)
    try:
        history_rows = table_count("price_history")
    except Exception:
        history_rows = -1
    return total, with_price, history_rows

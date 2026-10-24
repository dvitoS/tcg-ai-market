"""Glavna skripta: API -> čišćenje -> SQLite (tcg_market.db)."""

import sys

import requests
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from api_client import clean_cards, fetch_cards
from config import CATALOG_SERIES, DATABASE_NAME, TCG_API_KEY
from database import Card, PriceHistory, get_session, init_db
from generate_history import ensure_price_history


def save_cards(cards: list[dict]) -> int:
    """Sprema (ili ažurira) karte u bazu. Vraća broj obrađenih redaka."""
    if not cards:
        print("Nema karata za spremanje.")
        return 0

    session = get_session()
    try:
        stmt = sqlite_insert(Card).values(cards)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Card.id],
            set_={
                "name": stmt.excluded.name,
                "supertype": stmt.excluded.supertype,
                "rarity": stmt.excluded.rarity,
                "set_name": stmt.excluded.set_name,
                "market_price": stmt.excluded.market_price,
                "image_url": stmt.excluded.image_url,
            },
        )
        session.execute(stmt)
        session.commit()
        print(f"Spremljeno {len(cards)} karata u {DATABASE_NAME}.")
        return len(cards)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def print_summary() -> None:
    session = get_session()
    try:
        total = session.scalar(select(func.count()).select_from(Card)) or 0
        with_price = (
            session.scalar(
                select(func.count()).select_from(Card).where(Card.market_price.is_not(None))
            )
            or 0
        )
        history_rows = session.scalar(select(func.count()).select_from(PriceHistory)) or 0
        print(
            f"Sažetak baze: {total} karata, od toga {with_price} s cijenom, "
            f"{history_rows} redaka u price_history."
        )

        sample = session.scalars(select(Card).order_by(Card.name).limit(5)).all()
        if sample:
            print("Primjer karata:")
            for card in sample:
                price = f"{card.market_price:.2f}" if card.market_price is not None else "n/a"
                print(f"  - {card.name} ({card.id}) | {card.rarity or '?'} | {price}")
    finally:
        session.close()


def main() -> int:
    print("=== TCG Market: uvoz Pokémon karata ===")
    try:
        print(f"Inicijaliziram bazu '{DATABASE_NAME}'...")
        init_db()

        raw_cards = fetch_cards(series_names=CATALOG_SERIES, paginate=True)
        cleaned = clean_cards(raw_cards)
        save_cards(cleaned)
        if TCG_API_KEY:
            from sync_live_data import sync_live_price_history

            # Prvi uvoz: top PAGE_SIZE (rate limit). Noćni job sinkronizira sve.
            sync_live_price_history()
        else:
            print("TCG_API_KEY nije u .env. Povijest ostaje lokalna dok ne pokreneš sync_live_data.py.")
            ensure_price_history()
        print_summary()
        print("Gotovo.")
        return 0
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        print(f"HTTP greška ({status}) pri pozivu Pokémon TCG API-ja: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"Mrežna greška pri pozivu API-ja: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Neočekivana greška: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

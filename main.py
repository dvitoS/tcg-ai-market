"""Glavna skripta: API -> čišćenje -> Supabase (PostgreSQL)."""

import sys

import requests

from api_client import clean_cards, fetch_cards
from config import CATALOG_SERIES, TCG_API_KEY
from database import cards_summary, init_db, list_cards, upsert_cards
from generate_history import ensure_price_history


def save_cards(cards: list[dict]) -> int:
    """Sprema (ili ažurira) karte u Supabase. Vraća broj obrađenih redaka."""
    if not cards:
        print("Nema karata za spremanje.")
        return 0
    saved = upsert_cards(cards)
    print(f"Spremljeno {saved} karata u Supabase (cards).")
    return saved


def print_summary() -> None:
    total, with_price, history_rows = cards_summary()
    print(
        f"Sažetak baze: {total} karata, od toga {with_price} s cijenom, "
        f"{history_rows} redaka u price_history."
    )
    sample = list_cards(limit=5)
    if sample:
        print("Primjer karata:")
        for card in sample:
            price = f"{card.market_price:.2f}" if card.market_price is not None else "n/a"
            print(f"  - {card.name} ({card.id}) | {card.rarity or '?'} | {price}")


def main() -> int:
    print("=== TCG Market: uvoz Pokémon karata → Supabase ===")
    try:
        print("Inicijaliziram Supabase tablice...")
        init_db()

        raw_cards = fetch_cards(series_names=CATALOG_SERIES, paginate=True)
        cleaned = clean_cards(raw_cards)
        save_cards(cleaned)
        if TCG_API_KEY:
            from sync_live_data import sync_live_price_history

            sync_live_price_history()
        else:
            print("TCG_API_KEY nije u .env. Povijest ostaje lokalno generirana dok ne pokreneš sync.")
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

"""Povlači stvarnu povijest cijena s PokéWalleta u Supabase price_history."""

from __future__ import annotations

import sys

import requests

from api_client import TCGRateLimitError, fetch_card_price_history
from config import PAGE_SIZE, TCG_API_KEY
from database import Card, init_db, list_cards, replace_card_history, table_count


def top_cards(limit: int = PAGE_SIZE) -> list[Card]:
    return list_cards(limit=limit, order_price_desc=True)


def sync_live_price_history(limit: int | None = PAGE_SIZE) -> dict[str, int]:
    if not TCG_API_KEY:
        raise RuntimeError(
            "TCG_API_KEY nije postavljen. Dodaj ga u .env pa ponovno pokreni sync_live_data.py."
        )

    init_db()
    cards = list_cards(limit=limit, order_price_desc=True)
    if not cards:
        print("Nema karata u bazi. Prvo pokreni main.py.")
        return {"updated": 0, "skipped": 0, "saved": 0, "total_history": 0}

    scope = "sve karte" if limit is None else f"top {limit}"
    print(f"Sinkroniziram live povijest za {len(cards)} karata ({scope}, PokéWallet)...")
    saved = updated = skipped = 0
    for index, card in enumerate(cards, start=1):
        print(f"[{index}/{len(cards)}] {card.name} ({card.id})")
        try:
            points = fetch_card_price_history(card.id)
        except TCGRateLimitError:
            print("Dnevni ili trenutni rate limit je dosegnut. Zaustavljam sync.", file=sys.stderr)
            break
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            print(f"  HTTP {status} za {card.id}: {exc}", file=sys.stderr)
            if status in {401, 403}:
                print("Provjeri TCG_API_KEY i plan (povijest ovisi o tieru).", file=sys.stderr)
                break
            skipped += 1
            continue
        except requests.RequestException as exc:
            print(f"  Mrežna greška za {card.id}: {exc}", file=sys.stderr)
            skipped += 1
            continue

        if not points:
            skipped += 1
            continue

        written = replace_card_history(card.id, points)
        saved += written
        updated += 1
        print(f"  zamijenjeno {written} redaka u price_history.")

    total = table_count("price_history")
    print(
        f"Gotovo: {updated} karata ažurirano, {skipped} preskočeno, "
        f"{saved} novih cijena. price_history sada ima {total} redova."
    )
    return {
        "updated": updated,
        "skipped": skipped,
        "saved": saved,
        "total_history": int(total),
    }


def main() -> int:
    print("=== TCG Market: live povijest cijena ===")
    try:
        sync_live_price_history()
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Neočekivana greška: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

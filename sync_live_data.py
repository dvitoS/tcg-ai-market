"""Povlači stvarnu povijest cijena s PokéWalleta u tablicu price_history."""

from __future__ import annotations

import sys

import requests
from sqlalchemy import delete, func, select

from api_client import TCGRateLimitError, fetch_card_price_history
from config import PAGE_SIZE, TCG_API_KEY
from database import Card, PriceHistory, get_session, init_db


def list_cards(limit: int | None = PAGE_SIZE) -> list[Card]:
    """Karte po cijeni (skupo prvo). limit=None → sve karte u bazi."""
    session = get_session()
    try:
        query = select(Card).order_by(Card.market_price.desc())
        if limit is not None:
            query = query.limit(limit)
        return list(session.scalars(query).all())
    finally:
        session.close()


def top_cards(limit: int = PAGE_SIZE) -> list[Card]:
    return list_cards(limit=limit)


def replace_card_history(card_id: str, points: list[dict]) -> int:
    """Briše staru (simuliranu) povijest karte i upisuje API retke."""
    if not points:
        return 0

    session = get_session()
    try:
        session.execute(delete(PriceHistory).where(PriceHistory.card_id == card_id))
        session.bulk_insert_mappings(
            PriceHistory,
            [{"card_id": card_id, "date": point["date"], "price": point["price"]} for point in points],
        )
        session.commit()
        return len(points)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def sync_live_price_history(limit: int | None = PAGE_SIZE) -> dict[str, int]:
    """Dohvaća live povijest s PokéWalleta. limit=None → sve karte u bazi."""
    if not TCG_API_KEY:
        raise RuntimeError(
            "TCG_API_KEY nije postavljen. Dodaj ga u .env pa ponovno pokreni sync_live_data.py."
        )

    init_db()
    cards = list_cards(limit=limit)
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

    session = get_session()
    try:
        total = session.scalar(select(func.count()).select_from(PriceHistory)) or 0
    finally:
        session.close()

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
        # Bez argumenata: top PAGE_SIZE. Za sve karte: sync_live_price_history(limit=None)
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

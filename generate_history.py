"""Generira 60 dana logičnog trenda cijena u tablicu price_history."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

import numpy as np
from sqlalchemy import delete, func, select

from database import Card, PriceHistory, get_session, init_db

HISTORY_DAYS = 60
MIN_PRICE = 0.01
DAILY_OSCILLATION = 0.02

# Dnevni drift prije oscilacije. Dovoljno jak da preživi šum od ±2%
# kroz 60 dana: obične karte padaju, rjeđe rastu.
RARITY_DAILY_DRIFT = {
    "Common": -0.006,
    "Uncommon": -0.002,
    "Rare": 0.004,
    "Rare Holo": 0.005,
    "Double Rare": 0.008,
    "Ultra Rare": 0.010,
    "Illustration Rare": 0.011,
    "Special Illustration Rare": 0.012,
    "Hyper Rare": 0.013,
    "Secret Rare": 0.013,
}


def _card_seed(card_id: str) -> int:
    digest = hashlib.md5(card_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def daily_drift(card_id: str, rarity: str | None) -> float:
    """Stabilan drift po karti: rarity daje smjer, id daje mali raspon unutar grupe."""
    base = RARITY_DAILY_DRIFT.get(rarity or "Unknown", 0.0)
    bucket = _card_seed(card_id) % 7
    spread = (bucket - 3) * 0.00035
    return base + spread


def build_series(card_id: str, rarity: str | None, market_price: float, today: date) -> list[dict]:
    """60 točaka koje završavaju na današnjoj tržišnoj cijeni.

    Unatrag se skida drift (uzlazni trend znači da je jučer bilo jeftinije) i
    dnevna oscilacija ograničena na [-2%, +2%].
    """
    rng = np.random.default_rng(_card_seed(card_id))
    drift = daily_drift(card_id, rarity)
    price = float(market_price)
    points: list[tuple[date, float]] = [(today, round(price, 4))]

    for step in range(1, HISTORY_DAYS):
        oscillation = float(rng.uniform(-DAILY_OSCILLATION, DAILY_OSCILLATION))
        factor = max(1.0 + drift + oscillation, 0.5)
        price = max(price / factor, MIN_PRICE)
        points.append((today - timedelta(days=step), round(price, 4)))

    points.reverse()
    return [
        {"card_id": card_id, "date": day, "price": value}
        for day, value in points
    ]


def history_count(session) -> int:
    return int(session.scalar(select(func.count()).select_from(PriceHistory)) or 0)


def generate_price_history(*, replace: bool = False) -> int:
    """Upisuje 60 dana povijesti za svaku kartu s cijenom. Vraća broj novih redaka."""
    init_db()
    session = get_session()
    try:
        cards = session.scalars(select(Card).order_by(Card.id)).all()
        priced = [card for card in cards if card.market_price and card.market_price > 0]
        if not priced:
            print("Nema karata s cijenom. Prvo pokreni main.py.")
            return 0

        if replace:
            session.execute(delete(PriceHistory))
            session.commit()
            print("Obrisana postojeća price_history.")

        existing_ids = set(session.scalars(select(PriceHistory.card_id).distinct()).all())
        pending = [card for card in priced if card.id not in existing_ids]
        if not pending:
            print(f"Povijest već postoji za svih {len(priced)} karata. Preskačem.")
            return 0

        today = date.today()
        rows: list[dict] = []
        up = down = flat = 0
        for card in pending:
            series = build_series(card.id, card.rarity, float(card.market_price), today)
            rows.extend(series)
            start_price = series[0]["price"]
            end_price = series[-1]["price"]
            if end_price > start_price * 1.01:
                up += 1
            elif end_price < start_price * 0.99:
                down += 1
            else:
                flat += 1

        session.bulk_insert_mappings(PriceHistory, rows)
        session.commit()
        print(
            f"Upisano {len(rows)} cijena ({len(pending)} karata × {HISTORY_DAYS} dana). "
            f"Trendovi: {up} uzlaznih, {down} silaznih, {flat} gotovo ravnih."
        )
        return len(rows)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_price_history() -> int:
    """Punjava price_history samo ako je tablica prazna."""
    init_db()
    session = get_session()
    try:
        count = history_count(session)
    finally:
        session.close()

    if count > 0:
        print(f"price_history već ima {count} redaka. Inicijalizacija preskočena.")
        return 0

    print("price_history je prazna. Generiram 60 dana povijesti...")
    return generate_price_history(replace=False)


def main() -> int:
    print("=== TCG Market: generiranje povijesti cijena ===")
    try:
        generate_price_history(replace=True)
        return 0
    except Exception as exc:
        print(f"Greška pri generiranju povijesti: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Generira 60 dana logičnog trenda cijena u tablicu price_history (Supabase)."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

import numpy as np

from database import (
    clear_price_history,
    distinct_history_card_ids,
    init_db,
    insert_price_history,
    list_cards,
    table_count,
)

HISTORY_DAYS = 60
MIN_PRICE = 0.01
DAILY_OSCILLATION = 0.02

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
    base = RARITY_DAILY_DRIFT.get(rarity or "Unknown", 0.0)
    bucket = _card_seed(card_id) % 7
    spread = (bucket - 3) * 0.00035
    return base + spread


def build_series(card_id: str, rarity: str | None, market_price: float, today: date) -> list[dict]:
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


def generate_price_history(*, replace: bool = False) -> int:
    init_db()
    cards = list_cards()
    priced = [card for card in cards if card.market_price and card.market_price > 0]
    if not priced:
        print("Nema karata s cijenom. Prvo pokreni main.py.")
        return 0

    if replace:
        clear_price_history()
        print("Obrisana postojeća price_history.")

    existing_ids = distinct_history_card_ids()
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

    inserted = insert_price_history(rows)
    print(
        f"Upisano {inserted} cijena ({len(pending)} karata × {HISTORY_DAYS} dana). "
        f"Trendovi: {up} uzlaznih, {down} silaznih, {flat} gotovo ravnih."
    )
    return inserted


def ensure_price_history() -> int:
    init_db()
    count = table_count("price_history")
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

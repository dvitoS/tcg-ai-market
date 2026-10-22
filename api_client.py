"""Klijent za Pokémon TCG API (https://pokemontcg.io)."""

from time import sleep
from typing import Any

import requests

from config import (
    DEFAULT_SET_ID,
    DEFAULT_SET_NAME,
    MAX_RETRIES,
    PAGE_SIZE,
    POKEMON_TCG_API_URL,
    REQUEST_TIMEOUT_SECONDS,
)


def _extract_market_price(card: dict[str, Any]) -> float | None:
    """Uzima prvu dostupnu cijenu: TCGPlayer holofoil market, zatim Cardmarket."""
    tcgplayer = card.get("tcgplayer") or {}
    prices = tcgplayer.get("prices") or {}
    holofoil = prices.get("holofoil") or {}
    holofoil_market = holofoil.get("market")
    if holofoil_market is not None:
        try:
            return float(holofoil_market)
        except (TypeError, ValueError):
            pass

    cardmarket = card.get("cardmarket") or {}
    cm_prices = cardmarket.get("prices") or {}
    average_sell = cm_prices.get("averageSellPrice")
    if average_sell is not None:
        try:
            return float(average_sell)
        except (TypeError, ValueError):
            pass

    return None


def fetch_cards(
    set_name: str = DEFAULT_SET_NAME,
    set_id: str = DEFAULT_SET_ID,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Povlači prvih `page_size` karata iz zadanog seta."""
    params = {
        "q": f"set.id:{set_id}",
        "page": 1,
        "pageSize": page_size,
        "orderBy": "number",
    }
    headers = {"Accept": "application/json"}

    print(f"Dohvaćam {page_size} karata iz seta '{set_name}' ({set_id})...")
    last_error: Exception | None = None
    response = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                POKEMON_TCG_API_URL,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code >= 500:
                print(f"API je vratio {response.status_code} (pokušaj {attempt}/{MAX_RETRIES}).")
                last_error = requests.HTTPError(response=response)
                sleep(attempt)
                continue
            response.raise_for_status()
            break
        except requests.RequestException as exc:
            last_error = exc
            print(f"Greška pri dohvatu (pokušaj {attempt}/{MAX_RETRIES}): {exc}")
            sleep(attempt)
    else:
        if response is not None:
            response.raise_for_status()
        if last_error:
            raise last_error
        raise RuntimeError("Dohvat karata nije uspio.")

    payload = response.json()
    cards = payload.get("data") or []
    print(f"API je vratio {len(cards)} karata (ukupno u setu: {payload.get('totalCount', '?')}).")
    return cards


def clean_cards(raw_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalizira API odgovor u retke spremne za tablicu cards."""
    cleaned: list[dict[str, Any]] = []
    skipped = 0

    for card in raw_cards:
        card_id = card.get("id")
        if not card_id:
            skipped += 1
            continue

        set_info = card.get("set") or {}
        name = (card.get("name") or "").strip() or None

        cleaned.append(
            {
                "id": str(card_id),
                "name": name,
                "supertype": card.get("supertype"),
                "rarity": card.get("rarity"),
                "set_name": set_info.get("name"),
                "market_price": _extract_market_price(card),
            }
        )

    if skipped:
        print(f"Preskočeno {skipped} karata bez ID-a.")
    print(f"Očišćeno {len(cleaned)} karata.")
    return cleaned

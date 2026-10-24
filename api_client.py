"""Klijent za Pokémon TCG API (https://pokemontcg.io) i PokéWallet povijest cijena."""

import os
from datetime import date, timedelta
from time import sleep, time
from typing import Any

import requests
from dotenv import load_dotenv

from config import (
    API_REQUEST_DELAY_SECONDS,
    DEFAULT_SET_ID,
    DEFAULT_SET_NAME,
    ENV_PATH,
    MAX_RETRIES,
    PAGE_SIZE,
    POKEMON_TCG_API_URL,
    PRICE_HISTORY_DAYS,
    REQUEST_TIMEOUT_SECONDS,
    TCG_API_BASE_URL,
)

_last_tcg_request_at = 0.0


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


class TCGRateLimitError(requests.HTTPError):
    """API je vratio 429. Sync treba stati i sačuvati već upisane retke."""


def _tcg_api_key() -> str:
    """Čita TCG_API_KEY iz .env pri svakom zahtjevu."""
    load_dotenv(ENV_PATH, override=True)
    key = (os.getenv("TCG_API_KEY") or "").strip().strip('"').strip("'")
    if not key:
        raise RuntimeError(
            "TCG_API_KEY nije postavljen. U .env upiši TCG_API_KEY=tvoj_kljuc (https://pokewallet.io)."
        )
    return key


def _tcg_headers() -> dict[str, str]:
    return {
        "X-API-Key": _tcg_api_key(),
        "Accept": "application/json",
    }


def _tcg_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET na api.pokewallet.io s pauzom između zahtjeva i jednim čekanjem na 429."""
    global _last_tcg_request_at
    elapsed = time() - _last_tcg_request_at
    if _last_tcg_request_at and elapsed < API_REQUEST_DELAY_SECONDS:
        sleep(API_REQUEST_DELAY_SECONDS - elapsed)

    url = f"{TCG_API_BASE_URL}{path}"
    response = requests.get(url, params=params, headers=_tcg_headers(), timeout=REQUEST_TIMEOUT_SECONDS)
    _last_tcg_request_at = time()

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        wait = float(retry_after) if retry_after and retry_after.isdigit() else 2.0
        print(f"Rate limit (429). Čekam {wait:.0f}s pa ponavljam jednom...")
        sleep(wait)
        response = requests.get(url, params=params, headers=_tcg_headers(), timeout=REQUEST_TIMEOUT_SECONDS)
        _last_tcg_request_at = time()
        if response.status_code == 429:
            raise TCGRateLimitError(response=response)

    response.raise_for_status()
    hour_left = response.headers.get("X-RateLimit-Remaining-Hour")
    day_left = response.headers.get("X-RateLimit-Remaining-Day")
    if hour_left is not None or day_left is not None:
        print(f"  preostali zahtjevi: sat {hour_left or '?'}, dan {day_left or '?'}")
    return response.json()


def _card_number(card_id: str) -> str | None:
    if "-" not in card_id:
        return None
    return card_id.rsplit("-", 1)[-1].lstrip("0") or "0"


def _normalize_label(value: str | None) -> str:
    return (value or "").lower().replace("—", " ").replace("-", " ").replace("&", " and ")


def _same_number(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return left.lstrip("0") == right.lstrip("0")


def _base_name(value: str | None) -> str:
    return _normalize_label(value).split(" (", 1)[0].strip()


def resolve_pokewallet_card_id(card_id: str, name: str, set_name: str | None) -> str | None:
    """Traži PokéWallet ID (pk_...) preko imena, seta i broja karte."""
    if str(card_id).startswith("pk_"):
        return str(card_id)

    number = _card_number(card_id)
    query = f"{name} {number}" if number else name
    payload = _tcg_get("/search", {"q": query, "limit": 20})
    wanted_set = _normalize_label(set_name)
    wanted_name = _base_name(name)
    results = payload.get("results") or payload.get("data") or []

    for item in results:
        info = item.get("card_info") or item
        if _base_name(info.get("name")) != wanted_name:
            continue
        item_set = _normalize_label(info.get("set_name"))
        if wanted_set and item_set != wanted_set:
            continue
        if number and not _same_number(number, info.get("card_number") or info.get("number")):
            continue
        external_id = item.get("id")
        if external_id:
            return str(external_id)
    return None


def _as_price(value: Any) -> float | None:
    if value is None:
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def _best_variant(block: dict[str, Any] | None) -> dict[str, Any] | None:
    variants = (block or {}).get("variants") or {}
    if not isinstance(variants, dict) or not variants:
        return None
    lowered = {str(name).lower(): value for name, value in variants.items() if isinstance(value, dict)}
    for name in ("holofoil", "reverse holofoil", "normal"):
        if name in lowered:
            return lowered[name]
    return next(iter(lowered.values()), None)


def _snapshot_price(variant: dict[str, Any], field: str) -> float | None:
    if field == "current":
        current = variant.get("current") or {}
        return _as_price(current.get("market") if current.get("market") is not None else current.get("avg") or current.get("trend"))
    return _as_price(variant.get(field))


def history_points_from_payload(payload: dict[str, Any], *, today: date | None = None) -> list[dict[str, Any]]:
    """PokéWallet snimke (danas, 7, 14, 30, 60 dana) pretvara u retke price_history."""
    variant = _best_variant(payload.get("tcgplayer")) or _best_variant(payload.get("cardmarket"))
    if variant is None:
        return []

    anchor = today or date.today()
    updated = variant.get("last_updated")
    if updated:
        try:
            anchor = date.fromisoformat(str(updated)[:10])
        except ValueError:
            pass

    offsets = ((0, "current"), (7, "price_7d"), (14, "price_14d"), (30, "price_30d"), (60, "price_60d"))
    by_date: dict[date, float] = {}
    for days, field in offsets:
        if days > PRICE_HISTORY_DAYS:
            continue
        price = _snapshot_price(variant, field)
        if price is None:
            continue
        by_date[anchor - timedelta(days=days)] = price

    return [{"date": day, "price": round(price, 4)} for day, price in sorted(by_date.items())]


def _store_pokewallet_id(card_id: str, pokewallet_id: str) -> None:
    from database import Card, get_session

    session = get_session()
    try:
        card = session.get(Card, card_id)
        if card is None or card.pokewallet_id == pokewallet_id:
            return
        card.pokewallet_id = pokewallet_id
        session.commit()
        print(f"  spremljen pokewallet_id za {card_id}.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def fetch_card_price_history(card_id: str) -> list[dict[str, Any]]:
    """Povijest cijena s PokéWalleta preko cards.pokewallet_id.

    Endpoint: GET https://api.pokewallet.io/cards/{pokewallet_id}/price-history
    Zaglavlje: X-API-Key
    """
    from database import Card, get_session, init_db

    init_db()
    if str(card_id).startswith("pk_"):
        external_id = str(card_id)
    else:
        session = get_session()
        try:
            card = session.get(Card, card_id)
            if card is None or not card.name:
                print(f"Karta {card_id} nije u lokalnoj bazi.")
                return []
            external_id = card.pokewallet_id
            name = card.name
            set_name = card.set_name
        finally:
            session.close()

        if not external_id:
            external_id = resolve_pokewallet_card_id(card_id, name, set_name)
            if external_id:
                _store_pokewallet_id(card_id, external_id)

    if not external_id:
        print(f"PokéWallet nema podudaranje za {card_id}.")
        return []

    print(f"Povijest cijena za {card_id} (PokéWallet {external_id})...")
    payload = _tcg_get(f"/cards/{external_id}/price-history")
    points = history_points_from_payload(payload)
    print(f"  API je vratio {len(points)} snimki cijene.")
    return points

"""PokéWallet price-history client (TCG_API_KEY)."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from time import sleep, time
from typing import Any

import requests
from dotenv import load_dotenv

from config import (
    API_REQUEST_DELAY_SECONDS,
    ENV_PATH,
    MAX_RETRIES,
    PRICE_HISTORY_DAYS,
    RATE_LIMIT_RETRY_SLEEP_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    TCG_API_BASE_URL,
)

_last_tcg_request_at = 0.0
LOG = logging.getLogger("tcg.nightly")

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
    from database import get_card, update_card_pokewallet_id

    card = get_card(card_id)
    if card is None or card.pokewallet_id == pokewallet_id:
        return
    update_card_pokewallet_id(card_id, pokewallet_id)
    print(f"  spremljen pokewallet_id za {card_id}.")


def fetch_card_price_history(card_id: str) -> list[dict[str, Any]]:
    """Povijest cijena s PokéWalleta preko cards.pokewallet_id.

    Endpoint: GET https://api.pokewallet.io/cards/{pokewallet_id}/price-history
    Zaglavlje: X-API-Key
    """
    from database import get_card, init_db

    init_db()
    if str(card_id).startswith("pk_"):
        external_id = str(card_id)
    else:
        card = get_card(card_id)
        if card is None or not card.name:
            print(f"Karta {card_id} nije u Supabase bazi.")
            return []
        external_id = card.pokewallet_id
        name = card.name
        set_name = card.set_name

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

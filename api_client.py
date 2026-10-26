"""Klijent za Pokémon TCG API (https://pokemontcg.io) i PokéWallet povijest cijena."""

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
    AUTOMATION_LOG,
    CATALOG_HTTP_MAX_ATTEMPTS,
    CATALOG_SERIES,
    DEFAULT_SET_ID,
    DEFAULT_SET_NAME,
    ENV_PATH,
    MAX_RETRIES,
    PAGE_SIZE,
    POKEMON_TCG_API_URL,
    POKEMON_TCG_MAX_PAGE_SIZE,
    POKEMON_TCG_SETS_URL,
    PRICE_HISTORY_DAYS,
    RATE_LIMIT_RETRY_SLEEP_SECONDS,
    RATE_LIMIT_SLEEP_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    TCG_API_BASE_URL,
)

_last_tcg_request_at = 0.0
LOG = logging.getLogger("tcg.nightly")


def _as_positive_price(value: Any) -> float | None:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def _extract_market_price(card: dict[str, Any]) -> float | None:
    """Najbolja dostupna spot cijena (USD): max TCGPlayer market po varijantama, inače Cardmarket."""
    found: list[float] = []
    tcgplayer = card.get("tcgplayer") or {}
    prices = tcgplayer.get("prices")
    variants = prices.values() if isinstance(prices, dict) else []
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        for key in ("market", "mid", "directLow", "low"):
            price = _as_positive_price(variant.get(key))
            if price is not None:
                found.append(price)
                break

    if found:
        return max(found)

    cardmarket = card.get("cardmarket") or {}
    cm_prices = cardmarket.get("prices")
    if isinstance(cm_prices, dict):
        for key in ("averageSellPrice", "trendPrice", "avg30"):
            price = _as_positive_price(cm_prices.get(key))
            if price is not None:
                return price
    return None


def _append_automation_log(message: str, level: str = "WARNING") -> None:
    """Piše u automation.log i u logger (nightly Tee ga i dalje hvata)."""
    line = f"{datetime.now().isoformat(timespec='seconds')} | {level} | {message}"
    print(message)
    try:
        LOG.log(logging.WARNING if level == "WARNING" else logging.INFO, message)
    except Exception:
        pass
    try:
        with AUTOMATION_LOG.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def _pace_after_page(cards_fetched: int, *, context: str) -> None:
    """Nakon uspješnog dohvata do 100 karata čekaj 65 s (1 zahtjev / min)."""
    if cards_fetched <= 0:
        return
    print(
        f"  [rate-limit] {context}: povučeno {cards_fetched} karata/stavki. "
        f"Čekam {RATE_LIMIT_SLEEP_SECONDS}s prije sljedećeg zahtjeva..."
    )
    sleep(RATE_LIMIT_SLEEP_SECONDS)


def _pokemon_get(
    url: str,
    params: dict[str, Any],
    *,
    progress: str | None = None,
) -> dict[str, Any]:
    """GET na pokemontcg.io. 429 → 90 s; 5xx → eksponencijalni backoff (API je često nestabilan)."""
    headers = {"Accept": "application/json"}
    last_error: Exception | None = None
    response = None
    max_attempts = max(MAX_RETRIES, CATALOG_HTTP_MAX_ATTEMPTS)

    for attempt in range(1, max_attempts + 1):
        if progress:
            print(f"  → API zahtjev ({progress}), pokušaj {attempt}/{max_attempts}...")
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code == 429:
                msg = (
                    "[WARNING] Rate limit dosegnut. "
                    "Čekam 90 sekundi prije ponovnog pokušaja..."
                )
                _append_automation_log(msg, level="WARNING")
                sleep(RATE_LIMIT_RETRY_SLEEP_SECONDS)
                continue
            if response.status_code >= 500:
                wait = min(90, 8 * attempt)
                print(
                    f"API je vratio {response.status_code} (pokušaj {attempt}/{max_attempts}). "
                    f"Čekam {wait}s..."
                )
                last_error = requests.HTTPError(
                    f"{response.status_code} Server Error for url: {response.url}",
                    response=response,
                )
                sleep(wait)
                continue
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as exc:
                if response.status_code == 429:
                    msg = (
                        "[WARNING] Rate limit dosegnut. "
                        "Čekam 90 sekundi prije ponovnog pokušaja..."
                    )
                    _append_automation_log(msg, level="WARNING")
                    sleep(RATE_LIMIT_RETRY_SLEEP_SECONDS)
                    continue
                last_error = exc
                print(f"HTTP greška ({response.status_code}): {exc}")
                sleep(min(30, 3 * attempt))
                continue
            return response.json()
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 429:
                msg = (
                    "[WARNING] Rate limit dosegnut. "
                    "Čekam 90 sekundi prije ponovnog pokušaja..."
                )
                _append_automation_log(msg, level="WARNING")
                sleep(RATE_LIMIT_RETRY_SLEEP_SECONDS)
                continue
            last_error = exc
            print(f"HTTP greška pri dohvatu (pokušaj {attempt}/{max_attempts}): {exc}")
            sleep(min(30, 3 * attempt))
        except requests.RequestException as exc:
            last_error = exc
            print(f"Greška pri dohvatu (pokušaj {attempt}/{max_attempts}): {exc}")
            sleep(min(30, 3 * attempt))

    if response is not None and response.status_code == 429:
        raise requests.exceptions.HTTPError(
            f"Rate limit 429 nakon {max_attempts} pokušaja.",
            response=response,
        )
    if response is not None and response.status_code >= 400:
        raise requests.exceptions.HTTPError(
            f"{response.status_code} Server Error for url: {response.url}",
            response=response,
        )
    if last_error:
        raise last_error
    raise RuntimeError("Dohvat s Pokémon TCG API-ja nije uspio.")


def fetch_sets_for_series(series_names: list[str] | tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    """Dohvaća setove za jednu ili više era (npr. Scarlet & Violet, Sword & Shield)."""
    names = list(series_names or CATALOG_SERIES)
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    page_size = min(PAGE_SIZE, POKEMON_TCG_MAX_PAGE_SIZE)

    for series in names:
        print(f"Dohvaćam popis setova za seriju '{series}'...")
        page = 1
        while True:
            print(f"  [napredak] serija '{series}' · stranica setova {page}...")
            payload = _pokemon_get(
                POKEMON_TCG_SETS_URL,
                {
                    "q": f'series:"{series}"',
                    "page": page,
                    "pageSize": page_size,
                    "orderBy": "-releaseDate",
                },
                progress=f"sets '{series}' page {page}",
            )
            batch = payload.get("data") or []
            if not batch:
                break
            for item in batch:
                set_id = str(item.get("id") or "")
                if not set_id or set_id in seen:
                    continue
                seen.add(set_id)
                collected.append(item)
            print(
                f"  [napredak] serija '{series}' · stranica {page}: "
                f"+{len(batch)} setova (ukupno {len(collected)})"
            )
            total = int(payload.get("totalCount") or 0)
            finished = page * page_size >= total or len(batch) < page_size
            if not finished:
                _pace_after_page(len(batch), context=f"sets '{series}' page {page}")
                page += 1
            else:
                # I između serija držimo 1 zahtjev / min ako je batch pun.
                if len(batch) >= page_size:
                    _pace_after_page(len(batch), context=f"sets '{series}' page {page} (zadnja puna)")
                break

    collected.sort(key=lambda item: str(item.get("releaseDate") or ""), reverse=True)
    print(f"Pronađeno {len(collected)} setova u {len(names)} serija.")
    return collected


def fetch_cards_for_set(
    set_id: str,
    *,
    set_name: str | None = None,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Povlači SVE karte jednog seta kroz paginaciju (max 250 / zahtjev + 65 s pauze)."""
    label = set_name or set_id
    page_size = min(int(page_size), POKEMON_TCG_MAX_PAGE_SIZE)
    print(f"Dohvaćam karte iz seta '{label}' ({set_id}), pageSize={page_size}...")
    cards: list[dict[str, Any]] = []
    page = 1
    total_count: int | None = None

    while True:
        print(f"  [napredak] set '{label}' · stranica {page}...")
        # orderBy ponekad okida 500 na pokemontcg.io — prvo s orderBy, fallback bez.
        try:
            payload = _pokemon_get(
                POKEMON_TCG_API_URL,
                {
                    "q": f"set.id:{set_id}",
                    "page": page,
                    "pageSize": page_size,
                    "orderBy": "number",
                },
                progress=f"cards '{label}' page {page}",
            )
        except (requests.HTTPError, requests.RequestException, RuntimeError) as primary_exc:
            print(
                f"  [fallback] set '{label}' page {page} bez orderBy "
                f"nakon greške: {primary_exc}"
            )
            sleep(RATE_LIMIT_SLEEP_SECONDS)
            payload = _pokemon_get(
                POKEMON_TCG_API_URL,
                {
                    "q": f"set.id:{set_id}",
                    "page": page,
                    "pageSize": page_size,
                },
                progress=f"cards '{label}' page {page} (no orderBy)",
            )
        batch = payload.get("data") or []
        if total_count is None:
            total_count = int(payload.get("totalCount") or 0)
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            print(f"  ukupno u setu: {total_count} karata (~{total_pages} stranica)")
        if not batch:
            break
        cards.extend(batch)
        print(
            f"  [napredak] set '{label}' · stranica {page}/{max(1, (total_count + page_size - 1) // page_size)}: "
            f"+{len(batch)} karata (dosad {len(cards)}/{total_count})"
        )
        finished = page * page_size >= total_count or len(batch) < page_size
        if finished:
            break
        _pace_after_page(len(batch), context=f"cards '{label}' page {page}")
        page += 1

    print(f"Set '{label}': {len(cards)} karata.")
    return cards


def fetch_cards(
    set_name: str = DEFAULT_SET_NAME,
    set_id: str = DEFAULT_SET_ID,
    page_size: int = PAGE_SIZE,
    *,
    set_ids: list[str] | None = None,
    series_names: list[str] | tuple[str, ...] | None = None,
    paginate: bool = True,
) -> list[dict[str, Any]]:
    """Povlači karte iz jednog ili više setova.

    - Bez `set_ids` / `series_names`: jedan set (`set_id`), s paginacijom ako je `paginate`.
    - S `series_names`: prvo dohvaća sve setove tih era, zatim sve karte.
    - S `set_ids`: samo navedeni setovi.
    Po setu: greška jednog seta ne prekida ostale (djelomični katalog).
    """
    page_size = min(int(page_size), POKEMON_TCG_MAX_PAGE_SIZE)
    targets: list[tuple[str, str]] = []

    if set_ids:
        targets = []
        for item in set_ids:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                targets.append((str(item[0]), str(item[1])))
            else:
                targets.append((str(item), str(item)))
    elif series_names is not None:
        catalog = fetch_sets_for_series(series_names)
        targets = [(str(item["id"]), str(item.get("name") or item["id"])) for item in catalog]
    elif paginate:
        targets = [(set_id, set_name)]
    else:
        print(f"Dohvaćam do {page_size} karata iz seta '{set_name}' ({set_id})...")
        payload = _pokemon_get(
            POKEMON_TCG_API_URL,
            {
                "q": f"set.id:{set_id}",
                "page": 1,
                "pageSize": page_size,
                "orderBy": "number",
            },
            progress=f"cards '{set_name}' page 1",
        )
        cards = payload.get("data") or []
        print(f"API je vratio {len(cards)} karata (ukupno u setu: {payload.get('totalCount', '?')}).")
        if len(cards) >= page_size:
            _pace_after_page(len(cards), context=f"cards '{set_name}' page 1")
        return cards

    if not targets:
        print("Nema setova za dohvat.")
        return []

    print(
        f"Dohvaćam karte iz {len(targets)} setova "
        f"(paginacija, pageSize={page_size}, pauza {RATE_LIMIT_SLEEP_SECONDS}s)..."
    )
    all_cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    failed: list[tuple[str, str, str]] = []

    def _ingest(set_cards: list[dict[str, Any]]) -> None:
        for card in set_cards:
            card_id = str(card.get("id") or "")
            if not card_id or card_id in seen:
                continue
            seen.add(card_id)
            all_cards.append(card)

    for index, (sid, label) in enumerate(targets, start=1):
        print(f"[{index}/{len(targets)}] set '{label}' ({sid})")
        try:
            set_cards = fetch_cards_for_set(sid, set_name=label, page_size=page_size)
            _ingest(set_cards)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            failed.append((sid, label, msg))
            _append_automation_log(
                f"Set '{label}' ({sid}) nije učitan — nastavljam s ostalima. {msg}",
                level="WARNING",
            )
            set_cards = []
        if index < len(targets):
            print(
                f"  [napredak] set {index}/{len(targets)} gotov. "
                f"Pauza {RATE_LIMIT_SLEEP_SECONDS}s prije sljedećeg seta..."
            )
            sleep(RATE_LIMIT_SLEEP_SECONDS)

    # Jedan ponovni prolaz za setove koji su pali (API 500 često nestane).
    if failed:
        print(f"Ponavljam {len(failed)} neuspjelih setova...")
        sleep(RATE_LIMIT_SLEEP_SECONDS)
        still_failed: list[tuple[str, str, str]] = []
        for sid, label, _prev in failed:
            try:
                set_cards = fetch_cards_for_set(sid, set_name=label, page_size=page_size)
                _ingest(set_cards)
                print(f"  retry OK: '{label}' ({sid}) → {len(set_cards)} karata")
            except Exception as exc:
                msg = f"{type(exc).__name__}: {exc}"
                still_failed.append((sid, label, msg))
                _append_automation_log(
                    f"Retry set '{label}' ({sid}) i dalje neuspješan. {msg}",
                    level="WARNING",
                )
            sleep(RATE_LIMIT_SLEEP_SECONDS)
        failed = still_failed

    print(f"Ukupno dohvaćeno {len(all_cards)} jedinstvenih karata.")
    if failed:
        names = ", ".join(f"{label} ({sid})" for sid, label, _ in failed)
        print(f"[WARNING] Setovi bez kompletnog dohvata: {names}")
    return all_cards


def pokemontcg_image_url(card_id: str) -> str | None:
    """CDN URL: https://images.pokemontcg.io/{set}/{number}.png"""
    if "-" not in str(card_id):
        return None
    set_code, number = str(card_id).rsplit("-", 1)
    if not set_code or not number:
        return None
    return f"https://images.pokemontcg.io/{set_code}/{number}.png"


def clean_cards(
    raw_cards: list[dict[str, Any]],
    *,
    min_price: float | None = None,
) -> list[dict[str, Any]]:
    """Normalizira API odgovor u retke spremne za tablicu cards.

    Ako je `min_price` zadan, odbacuje karte bez cijene ili ispod praga (USD).
    """
    cleaned: list[dict[str, Any]] = []
    skipped = 0
    below_min = 0

    for card in raw_cards:
        card_id = card.get("id")
        if not card_id:
            skipped += 1
            continue

        set_info = card.get("set") or {}
        name = (card.get("name") or "").strip() or None
        images = card.get("images") or {}
        image_url = images.get("small") or images.get("large")
        if not image_url:
            image_url = pokemontcg_image_url(str(card_id))

        market_price = _extract_market_price(card)
        if min_price is not None and (market_price is None or market_price < float(min_price)):
            below_min += 1
            continue

        cleaned.append(
            {
                "id": str(card_id),
                "name": name,
                "supertype": card.get("supertype"),
                "rarity": card.get("rarity"),
                "set_name": set_info.get("name") or set_info.get("id"),
                "market_price": market_price,
                "image_url": image_url,
            }
        )

    if skipped:
        print(f"Preskočeno {skipped} karata bez ID-a.")
    if below_min:
        print(f"Preskočeno {below_min} karata ispod ${float(min_price):.2f} (ili bez cijene).")
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

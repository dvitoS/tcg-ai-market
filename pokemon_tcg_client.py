"""Pokémon TCG API client (pokemontcg.io catalog + card fetch)."""


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
    REQUEST_TIMEOUT_SECONDS,
    TCG_API_BASE_URL,
    nightly_catalog_set_budget,
    pokemon_tcg_api_key,
    rate_limit_sleep_seconds,
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
    """Pace after a successful page — fast with API key, conservative without."""
    if cards_fetched <= 0:
        return
    wait = rate_limit_sleep_seconds()
    if wait <= 0:
        return
    print(
        f"  [rate-limit] {context}: povučeno {cards_fetched} karata/stavki. "
        f"Čekam {wait:g}s prije sljedećeg zahtjeva..."
    )
    sleep(wait)


def _pokemon_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    key = pokemon_tcg_api_key()
    if key:
        headers["X-Api-Key"] = key
    return headers


def _pokemon_get(
    url: str,
    params: dict[str, Any],
    *,
    progress: str | None = None,
) -> dict[str, Any]:
    """GET na pokemontcg.io. 429 → 90 s; 5xx → eksponencijalni backoff (API je često nestabilan)."""
    headers = _pokemon_headers()
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
                # 4xx (except 429) — do not burn retries (e.g. missing card 404).
                if 400 <= response.status_code < 500:
                    raise
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


def fetch_all_sets() -> list[dict[str, Any]]:
    """Svi Pokémon TCG setovi s pokemontcg.io (paginirano, bez series filtera)."""
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    page_size = min(PAGE_SIZE, POKEMON_TCG_MAX_PAGE_SIZE)
    page = 1
    print("Dohvaćam popis svih Pokémon TCG setova...")
    while True:
        print(f"  [napredak] all sets · stranica {page}...")
        payload = _pokemon_get(
            POKEMON_TCG_SETS_URL,
            {
                "page": page,
                "pageSize": page_size,
                "orderBy": "-releaseDate",
            },
            progress=f"sets all page {page}",
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
        total = int(payload.get("totalCount") or 0)
        print(
            f"  [napredak] all sets · stranica {page}: "
            f"+{len(batch)} (ukupno {len(collected)}/{total or '?'})"
        )
        finished = (total and page * page_size >= total) or len(batch) < page_size
        if finished:
            break
        _pace_after_page(len(batch), context=f"sets all page {page}")
        page += 1
    collected.sort(key=lambda item: str(item.get("releaseDate") or ""), reverse=True)
    print(f"Pronađeno {len(collected)} setova (svi).")
    return collected


def resolve_catalog_targets() -> list[tuple[str, str]]:
    """Aktivni (set_id, name) za nightly/main — svi setovi ili pinned lista."""
    from config import catalog_all_sets_enabled, catalog_sets

    if catalog_all_sets_enabled():
        try:
            rows = fetch_all_sets()
            targets = [
                (str(item["id"]), str(item.get("name") or item["id"]))
                for item in rows
                if item.get("id")
            ]
            if targets:
                return targets
            print("fetch_all_sets vratio 0 — fallback na curated catalog_sets().")
        except Exception as exc:
            print(f"fetch_all_sets failed ({exc}) — fallback na curated catalog_sets().")
    return [(sid, name) for sid, name in catalog_sets()]


def select_gapfill_catalog_targets(
    *,
    budget: int | None = None,
    db_counts: dict[str, int] | None = None,
    set_rows: list[dict[str, Any]] | None = None,
) -> tuple[list[tuple[str, str]], dict[str, int]]:
    """Pick incomplete/missing sets vs DB so nightly can finish without a full re-pull.

    Returns (targets, stats) where stats has keys:
      api_sets, complete, missing, incomplete, selected.
    """
    from database import card_counts_by_set_id

    rows = set_rows if set_rows is not None else fetch_all_sets()
    counts = db_counts if db_counts is not None else card_counts_by_set_id()
    limit = int(budget) if budget is not None else nightly_catalog_set_budget()
    limit = max(1, limit)

    missing: list[tuple[str, str, int, int]] = []
    incomplete: list[tuple[str, str, int, int]] = []
    complete = 0
    for item in rows:
        sid = str(item.get("id") or "").strip()
        if not sid:
            continue
        name = str(item.get("name") or sid)
        try:
            expected = int(item.get("total") or 0)
        except (TypeError, ValueError):
            expected = 0
        have = int(counts.get(sid) or 0)
        if expected > 0 and have >= expected:
            complete += 1
            continue
        if have <= 0:
            missing.append((sid, name, have, expected))
        else:
            incomplete.append((sid, name, have, expected))

    # Prefer empty sets, then farthest from complete, then newest (API order is -releaseDate).
    incomplete.sort(key=lambda row: (row[2] / row[3] if row[3] else 0.0, row[0]))
    ordered = missing + incomplete
    selected = [(sid, name) for sid, name, _h, _e in ordered[:limit]]
    stats = {
        "api_sets": len(rows),
        "complete": complete,
        "missing": len(missing),
        "incomplete": len(incomplete),
        "selected": len(selected),
        "budget": limit,
    }
    return selected, stats


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
    """Povlači SVE karte jednog seta kroz paginaciju (max 250 / zahtjev + paced sleep).

    Important: do **not** send ``orderBy``. On pokemontcg.io, ``orderBy=number``
    often returns HTTP 5xx *or* a 200 with broken page windows (page 2 overlaps
    page 1 → unique count stuck at pageSize, e.g. Ascended Heroes 250/295).
    Unordered paging is stable for ``set.id`` queries.
    """
    label = set_name or set_id
    page_size = min(int(page_size), POKEMON_TCG_MAX_PAGE_SIZE)
    print(f"Dohvaćam karte iz seta '{label}' ({set_id}), pageSize={page_size}...")
    cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    page = 1
    total_count: int | None = None

    while True:
        print(f"  [napredak] set '{label}' · stranica {page}...")
        payload = _pokemon_get(
            POKEMON_TCG_API_URL,
            {
                "q": f"set.id:{set_id}",
                "page": page,
                "pageSize": page_size,
            },
            progress=f"cards '{label}' page {page}",
        )
        batch = payload.get("data") or []
        if total_count is None:
            total_count = int(payload.get("totalCount") or 0)
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            print(f"  ukupno u setu: {total_count} karata (~{total_pages} stranica)")
        if not batch:
            break

        new_in_page = 0
        for card in batch:
            card_id = str(card.get("id") or "").strip()
            if not card_id or card_id in seen:
                continue
            seen.add(card_id)
            cards.append(card)
            new_in_page += 1

        total_pages = max(1, ((total_count or 0) + page_size - 1) // page_size)
        print(
            f"  [napredak] set '{label}' · stranica {page}/{total_pages}: "
            f"+{len(batch)} raw / +{new_in_page} new "
            f"(dosad {len(cards)}/{total_count})"
        )

        # Broken pagination: API claimed more cards but this page added nothing.
        if (
            total_count
            and len(cards) < total_count
            and new_in_page == 0
            and len(batch) > 0
        ):
            msg = (
                f"Set '{label}' ({set_id}): page {page} returned {len(batch)} "
                f"rows but 0 new ids (unique={len(cards)}/{total_count}). "
                "Stopping — likely unstable pokemontcg.io pagination."
            )
            _append_automation_log(msg, level="WARNING")
            break

        finished = (
            (total_count is not None and page * page_size >= total_count)
            or len(batch) < page_size
            or (total_count is not None and len(cards) >= total_count)
        )
        if finished:
            break
        _pace_after_page(len(batch), context=f"cards '{label}' page {page}")
        page += 1

    if total_count and len(cards) < total_count:
        msg = (
            f"Set '{label}' ({set_id}) incomplete after pagination: "
            f"unique={len(cards)} totalCount={total_count}."
        )
        _append_automation_log(msg, level="WARNING")
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
        # No orderBy — same broken window risk as fetch_cards_for_set.
        payload = _pokemon_get(
            POKEMON_TCG_API_URL,
            {
                "q": f"set.id:{set_id}",
                "page": 1,
                "pageSize": page_size,
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

    pace = rate_limit_sleep_seconds()
    print(
        f"Dohvaćam karte iz {len(targets)} setova "
        f"(paginacija, pageSize={page_size}, pauza {pace:g}s"
        f"{', API key' if pokemon_tcg_api_key() else ', bez API key'})..."
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

    def _try_tcgdex_fallback(sid: str, label: str) -> list[dict[str, Any]]:
        """CAT.2b: mapped Soft Ink set → TCGdex list, Soft Ink ids preserved."""
        try:
            from tcgdex_client import (
                tcgdex_catalog_fallback_enabled,
                tcgdex_set_card_rows_as_pokemontcg,
            )
        except Exception:
            return []
        if not tcgdex_catalog_fallback_enabled():
            return []
        try:
            rows = tcgdex_set_card_rows_as_pokemontcg(sid, set_name=label)
        except Exception as exc:
            _append_automation_log(
                f"CAT.2b TCGdex fallback failed for '{label}' ({sid}): {exc}",
                level="WARNING",
            )
            return []
        if rows:
            print(
                f"  CAT.2b TCGdex fallback: '{label}' ({sid}) → {len(rows)} karata"
            )
        return rows

    for index, (sid, label) in enumerate(targets, start=1):
        print(f"[{index}/{len(targets)}] set '{label}' ({sid})")
        try:
            set_cards = fetch_cards_for_set(sid, set_name=label, page_size=page_size)
            _ingest(set_cards)
            if not set_cards:
                fallback = _try_tcgdex_fallback(sid, label)
                _ingest(fallback)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            fallback = _try_tcgdex_fallback(sid, label)
            if fallback:
                _ingest(fallback)
            else:
                failed.append((sid, label, msg))
                _append_automation_log(
                    f"Set '{label}' ({sid}) nije učitan — nastavljam s ostalima. {msg}",
                    level="WARNING",
                )
        if index < len(targets) and pace > 0:
            print(
                f"  [napredak] set {index}/{len(targets)} gotov. "
                f"Pauza {pace:g}s prije sljedećeg seta..."
            )
            sleep(pace)

    # Jedan ponovni prolaz za setove koji su pali (API 500 često nestane).
    if failed:
        print(f"Ponavljam {len(failed)} neuspjelih setova...")
        if pace > 0:
            sleep(pace)
        still_failed: list[tuple[str, str, str]] = []
        for sid, label, _prev in failed:
            try:
                set_cards = fetch_cards_for_set(sid, set_name=label, page_size=page_size)
                _ingest(set_cards)
                if set_cards:
                    print(f"  retry OK: '{label}' ({sid}) → {len(set_cards)} karata")
                else:
                    fallback = _try_tcgdex_fallback(sid, label)
                    if fallback:
                        _ingest(fallback)
                    else:
                        still_failed.append((sid, label, _prev))
            except Exception as exc:
                msg = f"{type(exc).__name__}: {exc}"
                fallback = _try_tcgdex_fallback(sid, label)
                if fallback:
                    _ingest(fallback)
                else:
                    still_failed.append((sid, label, msg))
                    _append_automation_log(
                        f"Retry set '{label}' ({sid}) i dalje neuspješan. {msg}",
                        level="WARNING",
                    )
            if pace > 0:
                sleep(pace)
        failed = still_failed

    print(f"Ukupno dohvaćeno {len(all_cards)} jedinstvenih karata.")
    if failed:
        names = ", ".join(f"{label} ({sid})" for sid, label, _ in failed)
        print(f"[WARNING] Setovi bez kompletnog dohvata: {names}")
    return all_cards


def fetch_pokemon_card(card_id: str, *, quiet: bool = True) -> dict[str, Any] | None:
    """Single-card GET via `_pokemon_get` (retries 429/5xx; no PokéWallet key).

    Returns the `data` object or None when the card is missing / request fails quietly.
    """
    cid = str(card_id or "").strip()
    if not cid:
        return None
    url = f"{POKEMON_TCG_API_URL.rstrip('/')}/{cid}"
    progress = None if quiet else f"card {cid}"
    try:
        payload = _pokemon_get(url, {}, progress=progress)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status == 404:
            return None
        if quiet:
            LOG.warning("fetch_pokemon_card(%s) HTTP %s", cid, status)
            return None
        raise
    except Exception as exc:
        if quiet:
            LOG.warning("fetch_pokemon_card(%s) failed: %s", cid, exc)
            return None
        raise
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, dict) else None


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
        # Rewrite known-broken pokemontcg CDN sets to TCGdex assets (no API key).
        try:
            from tcgdex_client import prefer_card_image_url

            image_url = prefer_card_image_url(str(card_id), image_url) or image_url
        except Exception:
            pass

        market_price = _extract_market_price(card)
        # min_price <= 0 means "no floor" (same as None) so unpriced cards stay.
        floor = None if min_price is None or float(min_price) <= 0 else float(min_price)
        if floor is not None and (market_price is None or market_price < floor):
            below_min += 1
            continue

        from justtcg_client import extract_tcgplayer_product_id
        from services.card_finishes import extract_finishes_from_tcgplayer, finishes_blob

        finishes = finishes_blob(extract_finishes_from_tcgplayer(card))

        cleaned.append(
            {
                "id": str(card_id),
                "name": name,
                "supertype": card.get("supertype"),
                "rarity": card.get("rarity"),
                "set_name": set_info.get("name") or set_info.get("id"),
                "market_price": market_price,
                "tcgplayer_id": extract_tcgplayer_product_id(card),
                "finishes": finishes,
                "image_url": image_url,
            }
        )

    if skipped:
        print(f"Preskočeno {skipped} karata bez ID-a.")
    if below_min:
        print(f"Preskočeno {below_min} karata ispod ${float(min_price):.2f} (ili bez cijene).")
    print(f"Očišćeno {len(cleaned)} karata.")
    return cleaned


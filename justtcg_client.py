"""JustTCG API klijent — NM cijene + price history (Phase A)."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from time import sleep
from typing import Any

import requests

from config import (
    JUSTTCG_API_BASE_URL,
    JUSTTCG_API_KEY,
    JUSTTCG_BATCH_SIZE,
    JUSTTCG_HISTORY_DURATION,
    JUSTTCG_REQUEST_DELAY_SECONDS,
    _secret,
)

LOG = logging.getLogger("tcg.justtcg")

# Graded (PSA …) živi na /v2/cards (beta). v1 base ostaje za NM.
JUSTTCG_API_V2_BASE_URL = "https://api.justtcg.com/v2"
JUSTTCG_PSA10_HISTORY_INCLUDE = "periods.30d,periods.90d,periods.1y,price_history.90d"

# In-process response cache — skip delay on identical GETs within one app session.
_GET_CACHE: dict[str, dict[str, Any]] = {}
_GET_CACHE_MAX = 128


def _cache_key(base: str, path: str, params: dict[str, Any] | None) -> str:
    items = tuple(sorted((params or {}).items()))
    return f"{base}|{path}|{items}"


def clear_justtcg_cache() -> None:
    _GET_CACHE.clear()


class JustTCGRateLimitError(requests.HTTPError):
    """429 ili mjesečni/dnevni limit."""


def justtcg_api_key() -> str:
    """Uvijek svježe — ne oslanjaj se na stale JUSTTCG_API_KEY konstantu."""
    try:
        from config import get_justtcg_api_key

        return get_justtcg_api_key()
    except Exception:
        return (_secret("JUSTTCG_API_KEY") or JUSTTCG_API_KEY or "").strip()


def _headers() -> dict[str, str]:
    key = justtcg_api_key()
    if not key:
        raise RuntimeError(
            "JUSTTCG_API_KEY nije postavljen. Dodaj ga u .env / Streamlit Secrets / Actions."
        )
    return {"x-api-key": key, "Accept": "application/json", "Content-Type": "application/json"}


def _get(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    base_url: str | None = None,
) -> dict[str, Any]:
    root = (base_url or JUSTTCG_API_BASE_URL).rstrip("/")
    key = _cache_key(root, path, params)
    cached = _GET_CACHE.get(key)
    if cached is not None:
        return cached

    sleep(JUSTTCG_REQUEST_DELAY_SECONDS)
    url = f"{root}{path}"
    response = requests.get(url, params=params or {}, headers=_headers(), timeout=45)
    if response.status_code == 429:
        retry = response.headers.get("Retry-After", "6")
        wait = float(retry) if str(retry).replace(".", "", 1).isdigit() else 6.0
        LOG.warning("JustTCG 429 — čekam %.0fs", wait)
        sleep(wait)
        response = requests.get(url, params=params or {}, headers=_headers(), timeout=45)
        if response.status_code == 429:
            raise JustTCGRateLimitError(response=response)
    response.raise_for_status()
    payload = response.json()
    if len(_GET_CACHE) >= _GET_CACHE_MAX:
        # Drop an arbitrary old entry (insertion order).
        _GET_CACHE.pop(next(iter(_GET_CACHE)), None)
    _GET_CACHE[key] = payload
    return payload


def _get_v2(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return _get(path, params, base_url=JUSTTCG_API_V2_BASE_URL)


def _post(path: str, payload: Any) -> dict[str, Any]:
    sleep(JUSTTCG_REQUEST_DELAY_SECONDS)
    url = f"{JUSTTCG_API_BASE_URL.rstrip('/')}{path}"
    response = requests.post(url, json=payload, headers=_headers(), timeout=60)
    if response.status_code == 429:
        retry = response.headers.get("Retry-After", "6")
        wait = float(retry) if str(retry).replace(".", "", 1).isdigit() else 6.0
        LOG.warning("JustTCG 429 — čekam %.0fs", wait)
        sleep(wait)
        response = requests.post(url, json=payload, headers=_headers(), timeout=60)
        if response.status_code == 429:
            raise JustTCGRateLimitError(response=response)
    response.raise_for_status()
    return response.json()


def extract_tcgplayer_product_id(card: dict[str, Any]) -> str | None:
    """Iz pokemontcg.io kartice: product id iz tcgplayer.url."""
    tcg = card.get("tcgplayer") or {}
    url = str(tcg.get("url") or "")
    match = re.search(r"/product/(\d+)", url)
    if match:
        return match.group(1)
    product_id = tcg.get("productId") or tcg.get("product_id")
    if product_id is not None:
        return str(product_id)
    return None


def normalize_card_number(value: str | None) -> str:
    text = str(value or "").strip()
    if "/" in text:
        text = text.split("/", 1)[0].strip()
    return text.lstrip("0") or "0"


def pick_nm_variant(variants: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Preferiraj Near Mint Holofoil, zatim NM bilo koji printing, zatim prva s cijenom."""
    if not variants:
        return None

    def cond(v: dict[str, Any]) -> str:
        return str(v.get("condition") or "").strip().lower()

    def printing(v: dict[str, Any]) -> str:
        return str(v.get("printing") or "").strip().lower()

    def has_price(v: dict[str, Any]) -> bool:
        price = v.get("price")
        if price is None:
            price = v.get("lastKnownPrice")
        try:
            return price is not None and float(price) > 0
        except (TypeError, ValueError):
            return False

    nm = [v for v in variants if "near mint" in cond(v) or cond(v) in {"nm", "near_mint"}]
    pool = nm or variants
    for preferred in ("holofoil", "holo", "reverse holofoil", "reverse holo", "normal"):
        for variant in pool:
            if preferred in printing(variant) and has_price(variant):
                return variant
    for variant in pool:
        if has_price(variant):
            return variant
    return pool[0] if pool else None


def variant_price_usd(variant: dict[str, Any] | None) -> float | None:
    if not variant:
        return None
    for key in ("price", "lastKnownPrice"):
        raw = variant.get(key)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def _history_list_from_variant(variant: dict[str, Any]) -> list[Any]:
    for key in (
        "priceHistory",
        "price_history",
        "priceHistory30d",
        "price_history_30d",
        "priceHistory90d",
    ):
        raw = variant.get(key)
        if isinstance(raw, list) and raw:
            return raw
    return []


def history_points_from_variant(variant: dict[str, Any] | None) -> list[dict[str, Any]]:
    """JustTCG priceHistory [{p,t}] → [{date, price}] (USD)."""
    if not variant:
        return []
    points: list[dict[str, Any]] = []
    history = _history_list_from_variant(variant)
    for item in history:
        if not isinstance(item, dict):
            continue
        price = item.get("p", item.get("price"))
        ts = item.get("t", item.get("timestamp"))
        try:
            price_f = float(price)
            ts_i = int(ts)
        except (TypeError, ValueError):
            continue
        if price_f <= 0:
            continue
        # Sekunde ili milisekunde.
        if ts_i > 10_000_000_000:
            ts_i //= 1000
        day = datetime.fromtimestamp(ts_i, tz=timezone.utc).date()
        points.append({"date": day, "price": round(price_f, 4)})

    # Ako history nema današnji spot, dodaj trenutnu cijenu.
    spot = variant_price_usd(variant)
    if spot is not None:
        today = date.today()
        if not any(p["date"] == today for p in points):
            points.append({"date": today, "price": round(spot, 4)})

    by_date: dict[date, float] = {}
    for point in sorted(points, key=lambda p: p["date"]):
        by_date[point["date"]] = float(point["price"])
    return [{"date": day, "price": price} for day, price in sorted(by_date.items())]


def fetch_card_by_tcgplayer_id(tcgplayer_id: str) -> dict[str, Any] | None:
    """Jedna karta po TCGplayer product id (POST batch, fallback GET)."""
    tid = str(tcgplayer_id or "").strip()
    if not tid:
        return None

    rows = batch_by_tcgplayer_ids([tid])
    if rows:
        return rows[0]

    payload = _get(
        "/cards",
        {
            "tcgplayerId": tid,
            "condition": "NM",
            "include_price_history": "true",
            "priceHistoryDuration": JUSTTCG_HISTORY_DURATION,
            "limit": 5,
        },
    )
    rows = list(payload.get("data") or [])
    return rows[0] if rows else None


def nm_history_for_tcgplayer_id(tcgplayer_id: str) -> list[dict[str, Any]]:
    """NM price history points za product id (može biti samo spot ako API nema history)."""
    card = fetch_card_by_tcgplayer_id(tcgplayer_id)
    if not card:
        return []
    variant = pick_nm_variant(list(card.get("variants") or []))
    return history_points_from_variant(variant)


def _card_number_matches(row_number: str | None, wanted: str) -> bool:
    if not wanted:
        return False
    raw = str(row_number or "").strip()
    if not raw:
        return False
    if normalize_card_number(raw) == wanted:
        return True
    # "215/203" vs wanted "215"
    left = normalize_card_number(raw.split("/", 1)[0])
    return left == wanted


def _score_search_row(
    row: dict[str, Any],
    *,
    wanted_name: str,
    wanted_number: str,
    wanted_set: str,
) -> int:
    score = 0
    name = str(row.get("name") or "").strip().lower()
    if wanted_name and name == wanted_name:
        score += 50
    elif wanted_name and wanted_name in name:
        score += 20
    if wanted_number and _card_number_matches(row.get("number"), wanted_number):
        score += 100
    set_obj = row.get("set") if isinstance(row.get("set"), dict) else {}
    set_name = str(row.get("set_name") or set_obj.get("name") or "").strip().lower()
    if wanted_set and set_name == wanted_set:
        score += 40
    elif wanted_set and wanted_set in set_name:
        score += 15
    variant = pick_nm_variant(list(row.get("variants") or []))
    if history_points_from_variant(variant):
        score += 5
    return score


def _search_cards_raw(q: str, *, limit: int = 20) -> list[dict[str, Any]]:
    query = (q or "").strip()
    if not query:
        return []
    # Free tier rejects limits above ~20.
    safe_limit = max(1, min(int(limit), JUSTTCG_BATCH_SIZE))
    payload = _get(
        "/cards",
        {
            "game": "pokemon",
            "q": query,
            "condition": "NM",
            "include_price_history": "true",
            "priceHistoryDuration": JUSTTCG_HISTORY_DURATION,
            "limit": safe_limit,
        },
    )
    return list(payload.get("data") or [])


def search_pokemon_card(
    *,
    name: str,
    number: str | None = None,
    set_name: str | None = None,
) -> dict[str, Any] | None:
    """Pronađi JustTCG kartu — preferiraj name+number (set u queryu često pokvari match)."""
    wanted_name = (name or "").strip().lower()
    wanted_number = normalize_card_number(number) if number else ""
    wanted_set = (set_name or "").strip().lower()
    if not wanted_name and not wanted_number:
        return None

    # Order matters: number-first queries are much more precise for secret/alt arts.
    queries: list[str] = []
    if wanted_name and wanted_number:
        queries.append(f"{name} {wanted_number}".strip())
    if wanted_name:
        queries.append(str(name).strip())
    if wanted_name and wanted_set:
        queries.append(f"{name} {set_name}".strip())
    if wanted_name and wanted_number and wanted_set:
        queries.append(f"{name} {wanted_number} {set_name}".strip())

    best: dict[str, Any] | None = None
    best_score = -1
    seen_q: set[str] = set()
    for q in queries:
        key = q.lower()
        if not q or key in seen_q:
            continue
        seen_q.add(key)
        try:
            rows = _search_cards_raw(q, limit=JUSTTCG_BATCH_SIZE)
        except Exception as exc:
            LOG.warning("JustTCG search failed q=%r: %s", q, exc)
            continue
        for row in rows:
            score = _score_search_row(
                row,
                wanted_name=wanted_name,
                wanted_number=wanted_number,
                wanted_set=wanted_set,
            )
            if score > best_score:
                best = row
                best_score = score
        # Strong number+name hit — stop early.
        if best is not None and wanted_number and best_score >= 150:
            break

    return best


def nm_history_for_card(
    *,
    tcgplayer_id: str | None = None,
    name: str | None = None,
    number: str | None = None,
    set_name: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Vrati (points, resolved_tcgplayer_id). Probaj product id, zatim ranked search."""
    resolved: str | None = str(tcgplayer_id).strip() if tcgplayer_id else None
    if resolved:
        points = nm_history_for_tcgplayer_id(resolved)
        if points:
            return points, resolved

    card = search_pokemon_card(name=str(name or ""), number=number, set_name=set_name)
    if not card:
        return [], resolved
    resolved = str(card.get("tcgplayerId") or resolved or "") or resolved
    variant = pick_nm_variant(list(card.get("variants") or []))
    points = history_points_from_variant(variant)
    # If the top match has no series, try other strong number matches via a fresh number query.
    if not points and number:
        try:
            rows = _search_cards_raw(
                f"{name} {normalize_card_number(number)}".strip(),
                limit=JUSTTCG_BATCH_SIZE,
            )
            wanted = normalize_card_number(number)
            for row in rows:
                if not _card_number_matches(row.get("number"), wanted):
                    continue
                variant = pick_nm_variant(list(row.get("variants") or []))
                points = history_points_from_variant(variant)
                if points:
                    resolved = str(row.get("tcgplayerId") or resolved or "") or resolved
                    break
        except Exception as exc:
            LOG.warning("JustTCG number retry failed: %s", exc)
    return points, resolved


def list_pokemon_sets() -> list[dict[str, Any]]:
    payload = _get("/sets", {"game": "pokemon"})
    return list(payload.get("data") or [])


def resolve_set_id(set_name: str, *, cache: dict[str, str] | None = None) -> str | None:
    """Mapira naše ime seta (npr. '151') na JustTCG set id."""
    wanted = (set_name or "").strip().lower()
    if not wanted:
        return None
    if cache is not None and wanted in cache:
        return cache[wanted]

    payload = _get("/sets", {"game": "pokemon", "q": set_name})
    rows = list(payload.get("data") or [])
    if not rows:
        rows = list_pokemon_sets()

    exact = next((r for r in rows if str(r.get("name") or "").strip().lower() == wanted), None)
    chosen = exact or (rows[0] if rows else None)
    set_id = str(chosen["id"]) if chosen and chosen.get("id") else None
    if cache is not None and set_id:
        cache[wanted] = set_id
    return set_id


def fetch_set_cards_page(
    set_id: str,
    *,
    offset: int = 0,
    limit: int = JUSTTCG_BATCH_SIZE,
) -> tuple[list[dict[str, Any]], bool]:
    """Jedna stranica karata seta s NM filterom i history."""
    payload = _get(
        "/cards",
        {
            "game": "pokemon",
            "set": set_id,
            "condition": "NM",
            "priceHistoryDuration": JUSTTCG_HISTORY_DURATION,
            "include_price_history": "true",
            "limit": min(int(limit), JUSTTCG_BATCH_SIZE),
            "offset": int(offset),
        },
    )
    rows = list(payload.get("data") or [])
    meta = payload.get("meta") or {}
    has_more = bool(meta.get("hasMore"))
    return rows, has_more


def batch_by_tcgplayer_ids(tcgplayer_ids: list[str]) -> list[dict[str, Any]]:
    """POST batch lookup (max JUSTTCG_BATCH_SIZE)."""
    if not tcgplayer_ids:
        return []
    body = [
        {"tcgplayerId": str(tid), "condition": "NM"}
        for tid in tcgplayer_ids[:JUSTTCG_BATCH_SIZE]
    ]
    # History duration je query na GET; za batch pokušaj kao query param ako API podržava.
    payload = _post(
        f"/cards?priceHistoryDuration={JUSTTCG_HISTORY_DURATION}&include_price_history=true",
        body,
    )
    return list(payload.get("data") or [])


def pick_psa10_variant(variants: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Prvi PSA 10 graded variant (bez qualifiera ako je moguće)."""
    graded: list[dict[str, Any]] = []
    for variant in variants or []:
        if str(variant.get("type") or "").lower() != "graded":
            continue
        grading = variant.get("grading") or {}
        company = str(grading.get("company") or "").upper()
        try:
            grade = float(grading.get("grade"))
        except (TypeError, ValueError):
            continue
        if company != "PSA" or grade != 10.0:
            continue
        graded.append(variant)
    if not graded:
        return None

    def _rank(v: dict[str, Any]) -> tuple[int, int]:
        grading = v.get("grading") or {}
        has_qual = 1 if grading.get("qualifier") else 0
        priced = 0 if _market_price_usd(v) is None else -1
        return (has_qual, priced)

    return sorted(graded, key=_rank)[0]


def _market_entries(variant: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not variant:
        return []
    markets = variant.get("markets")
    if isinstance(markets, list) and markets:
        return [m for m in markets if isinstance(m, dict)]
    # v1-shaped fallback (flat price on variant)
    return [variant]


def _prefer_na_market(markets: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not markets:
        return None
    for region in ("NA", "US", "USA"):
        for market in markets:
            if str(market.get("region") or "").upper() == region:
                return market
    return markets[0]


def _market_price_usd(variant: dict[str, Any] | None) -> float | None:
    market = _prefer_na_market(_market_entries(variant))
    if not market:
        return None
    for key in ("price", "last_price", "lastKnownPrice"):
        raw = market.get(key)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return variant_price_usd(variant)


def history_points_from_v2_variant(variant: dict[str, Any] | None) -> list[dict[str, Any]]:
    """v2 markets[].price_history [{t,p}] → [{date, price}]; spot fallback ako je history prazan."""
    if not variant:
        return []
    market = _prefer_na_market(_market_entries(variant))
    if not market:
        return history_points_from_variant(variant)

    # Privremeno mapiraj market kao "variant" za postojeći parser.
    synthetic = {
        "price": market.get("price"),
        "lastKnownPrice": market.get("last_price"),
        "price_history": market.get("price_history") or market.get("priceHistory") or [],
    }
    points = history_points_from_variant(synthetic)
    if points:
        return points
    spot = _market_price_usd(variant)
    if spot is None:
        return []
    return [{"date": date.today(), "price": round(spot, 4)}]


def psa10_stats_from_variant(variant: dict[str, Any] | None) -> dict[str, Any]:
    """Agregati iz markets[].periods (sales_count itd.) + spot."""
    market = _prefer_na_market(_market_entries(variant)) or {}
    periods = market.get("periods") if isinstance(market.get("periods"), dict) else {}
    window = None
    for key in ("1y", "90d", "30d", "7d", "all_time"):
        if key in periods and isinstance(periods[key], dict):
            window = key
            break
    stats = dict(periods.get(window) or {}) if window else {}
    return {
        "price": _market_price_usd(variant),
        "currency": str(market.get("currency") or "USD"),
        "price_status": str(market.get("price_status") or ""),
        "updated_at": market.get("updated_at"),
        "period_key": window,
        "sales_count": stats.get("sales_count"),
        "avg": stats.get("avg"),
        "min": stats.get("min"),
        "max": stats.get("max"),
        "change_pct": stats.get("change_pct"),
        "canonical": ((variant or {}).get("grading") or {}).get("canonical") or "PSA 10",
        "has_history_series": bool(
            (market.get("price_history") or market.get("priceHistory") or [])
        ),
    }


def fetch_psa10_card_by_tcgplayer_id(tcgplayer_id: str) -> dict[str, Any] | None:
    """GET /v2/cards — samo PSA 10 graded variant."""
    tid = str(tcgplayer_id or "").strip()
    if not tid:
        return None
    payload = _get_v2(
        "/cards",
        {
            "tcgplayer_id": tid,
            "graded": "only",
            "grading_company": "PSA",
            "grade": "10",
            "include": JUSTTCG_PSA10_HISTORY_INCLUDE,
            "regions": "NA",
            "limit": 5,
        },
    )
    rows = list(payload.get("data") or [])
    return rows[0] if rows else None


def search_psa10_pokemon_card(
    *,
    name: str,
    number: str | None = None,
    set_name: str | None = None,
) -> dict[str, Any] | None:
    """Search /v2/cards za PSA 10."""
    query = " ".join(part for part in (name, number) if part).strip()
    if not query:
        return None
    q = f"{query} {set_name}".strip() if set_name else query
    payload = _get_v2(
        "/cards",
        {
            "game": "pokemon",
            "q": q,
            "graded": "only",
            "grading_company": "PSA",
            "grade": "10",
            "include": JUSTTCG_PSA10_HISTORY_INCLUDE,
            "regions": "NA",
            "limit": 20,
        },
    )
    rows = list(payload.get("data") or [])
    if not rows:
        return None
    wanted_number = normalize_card_number(number) if number else ""
    if wanted_number:
        for row in rows:
            if normalize_card_number(str(row.get("number") or "")) == wanted_number:
                return row
    wanted_name = (name or "").strip().lower()
    exact = next(
        (r for r in rows if str(r.get("name") or "").strip().lower() == wanted_name),
        None,
    )
    return exact or rows[0]


def psa10_history_for_card(
    *,
    tcgplayer_id: str | None = None,
    name: str | None = None,
    number: str | None = None,
    set_name: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any]]:
    """(points, resolved_tcgplayer_id, stats).

    Napomena: JustTCG v2 graded često ima spot + periods.sales_count,
    a price_history serija je još često prazna (beta coverage).
    """
    resolved: str | None = str(tcgplayer_id).strip() if tcgplayer_id else None
    card: dict[str, Any] | None = None
    if resolved:
        card = fetch_psa10_card_by_tcgplayer_id(resolved)
    if not card:
        card = search_psa10_pokemon_card(
            name=str(name or ""),
            number=number,
            set_name=set_name,
        )
    if not card:
        return [], resolved, {}

    external = card.get("external_ids") if isinstance(card.get("external_ids"), dict) else {}
    resolved = (
        str(external.get("tcgplayer") or card.get("tcgplayerId") or resolved or "") or resolved
    )
    variant = pick_psa10_variant(list(card.get("variants") or []))
    if not variant:
        return [], resolved, {}
    points = history_points_from_v2_variant(variant)
    stats = psa10_stats_from_variant(variant)
    return points, resolved, stats

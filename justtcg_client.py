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

# NM + graded cards: prefer /v2/cards (beta). /sets and /games stay on v1.
# Docs: https://justtcg.com/docs/api/cards-v2
JUSTTCG_API_V2_BASE_URL = "https://api.justtcg.com/v2"
JUSTTCG_PSA10_HISTORY_INCLUDE = "periods.30d,periods.90d,periods.1y,price_history.90d"
# v2 examples use game id "pokemon" (not display name "Pokemon").
JUSTTCG_GAME = "pokemon"
JUSTTCG_REGION = "NA"

# In-process response cache — skip delay on identical GETs/POSTs within one process.
_GET_CACHE: dict[str, dict[str, Any]] = {}
_POST_CACHE: dict[str, dict[str, Any]] = {}
_GET_CACHE_MAX = 128
_POST_CACHE_MAX = 64
# Process-local network request counter (cache hits do not count).
_REQUEST_COUNT = 0
_REQUEST_BUDGET: int | None = None
# Trip after repeated hard failures so a flaky upstream cannot burn the daily quota.
_CONSECUTIVE_FAILURES = 0
_FAILURE_CIRCUIT_THRESHOLD = 8


def _cache_key(base: str, path: str, params: dict[str, Any] | None) -> str:
    items = tuple(sorted((params or {}).items()))
    return f"{base}|{path}|{items}"


def _post_cache_key(path: str, payload: Any, *, base_url: str | None = None) -> str:
    """Stable key for JSON-serializable batch bodies."""
    import json

    root = (base_url or JUSTTCG_API_BASE_URL).rstrip("/")
    try:
        body = json.dumps(payload, sort_keys=True, default=str)
    except TypeError:
        body = repr(payload)
    return f"POST|{root}|{path}|{body}"


def clear_justtcg_cache() -> None:
    _GET_CACHE.clear()
    _POST_CACHE.clear()


def justtcg_request_count() -> int:
    return int(_REQUEST_COUNT)


def reset_justtcg_request_count() -> None:
    global _REQUEST_COUNT, _CONSECUTIVE_FAILURES
    _REQUEST_COUNT = 0
    _CONSECUTIVE_FAILURES = 0


def configure_justtcg_request_budget(max_requests: int | None) -> None:
    """Cap outbound JustTCG calls for this process (None = unlimited).

    Account is ~1000/day and ~10k/month. Nightly defaults to ~100 so Soft Ink +
    nightly fit in ≤~9k/month.
    """
    global _REQUEST_BUDGET, _CONSECUTIVE_FAILURES
    _CONSECUTIVE_FAILURES = 0
    if max_requests is None:
        _REQUEST_BUDGET = None
        return
    _REQUEST_BUDGET = max(1, int(max_requests))
    LOG.info("JustTCG request budget: %s", _REQUEST_BUDGET)


def _consume_request_budget() -> None:
    """Increment counter; raise before the HTTP call if the soft budget is spent."""
    global _REQUEST_COUNT
    if _REQUEST_BUDGET is not None and _REQUEST_COUNT >= _REQUEST_BUDGET:
        raise JustTCGRateLimitError(
            f"JustTCG request budget exhausted ({_REQUEST_COUNT}/{_REQUEST_BUDGET})",
            response=None,
        )
    _REQUEST_COUNT += 1


def _note_justtcg_success() -> None:
    global _CONSECUTIVE_FAILURES
    _CONSECUTIVE_FAILURES = 0


def _note_justtcg_failure(exc: BaseException) -> None:
    """Count consecutive hard failures; open circuit before another burn storm."""
    global _CONSECUTIVE_FAILURES
    _CONSECUTIVE_FAILURES += 1
    if _CONSECUTIVE_FAILURES < _FAILURE_CIRCUIT_THRESHOLD:
        return
    raise JustTCGRateLimitError(
        f"JustTCG circuit open after {_CONSECUTIVE_FAILURES} consecutive "
        f"failures (last={type(exc).__name__}: {exc})",
        response=getattr(exc, "response", None),
    ) from exc


class JustTCGRateLimitError(requests.HTTPError):
    """429, mjesečni/dnevni limit, lokalni request budget, ili failure circuit."""


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


def _v2_history_include() -> str:
    """Narrow periods + price_history windows (docs: include=periods.Xd,price_history.Xd)."""
    duration = str(JUSTTCG_HISTORY_DURATION or "90d").strip() or "90d"
    return f"periods.{duration},price_history.{duration}"


def _v2_raw_params(**extra: Any) -> dict[str, Any]:
    """GET/POST /v2/cards for raw NM — graded=exclude keeps base request cost."""
    params: dict[str, Any] = {
        "regions": JUSTTCG_REGION,
        "graded": "exclude",
        "include": _v2_history_include(),
    }
    params.update(extra)
    return params


def _v2_spot_params(**extra: Any) -> dict[str, Any]:
    """Portfolio/trade spots — periods only, no price_history series."""
    params: dict[str, Any] = {
        "regions": JUSTTCG_REGION,
        "graded": "exclude",
        "include": "periods.30d",
    }
    params.update(extra)
    return params


def _v2_batch_path(*, history: bool) -> str:
    """POST /v2/cards query string (include + regions apply to the whole batch)."""
    base = _v2_raw_params() if history else _v2_spot_params()
    qs = "&".join(f"{k}={v}" for k, v in sorted(base.items()))
    return f"/cards?{qs}"


def _parse_next_cursor(link_header: str | None) -> str | None:
    """Extract cursor from ``Link: <…&cursor=…>; rel="next"`` (v2 pagination)."""
    if not link_header:
        return None
    import re
    from urllib.parse import parse_qs, urlparse

    for part in str(link_header).split(","):
        if 'rel="next"' not in part and "rel=next" not in part:
            continue
        match = re.search(r"<([^>]+)>", part)
        if not match:
            continue
        query = parse_qs(urlparse(match.group(1)).query)
        cursors = query.get("cursor") or []
        if cursors and str(cursors[0]).strip():
            return str(cursors[0]).strip()
    return None


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

    _consume_request_budget()
    sleep(JUSTTCG_REQUEST_DELAY_SECONDS)
    url = f"{root}{path}"
    try:
        response = requests.get(url, params=params or {}, headers=_headers(), timeout=45)
        if response.status_code == 429:
            # Do not burn a second request — free-tier retries almost always 429 again.
            retry = response.headers.get("Retry-After")
            LOG.warning("JustTCG 429 (Retry-After=%s) — raising", retry or "?")
            raise JustTCGRateLimitError(response=response)
        response.raise_for_status()
        payload = response.json()
    except JustTCGRateLimitError:
        raise
    except Exception as exc:
        _note_justtcg_failure(exc)
        raise
    _note_justtcg_success()
    if len(_GET_CACHE) >= _GET_CACHE_MAX:
        # Drop an arbitrary old entry (insertion order).
        _GET_CACHE.pop(next(iter(_GET_CACHE)), None)
    _GET_CACHE[key] = payload
    return payload


def _get_v2(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return _get(path, params, base_url=JUSTTCG_API_V2_BASE_URL)


def _post(
    path: str,
    payload: Any,
    *,
    base_url: str | None = None,
) -> dict[str, Any]:
    root = (base_url or JUSTTCG_API_BASE_URL).rstrip("/")
    key = _post_cache_key(path, payload, base_url=root)
    cached = _POST_CACHE.get(key)
    if cached is not None:
        return cached

    _consume_request_budget()
    sleep(JUSTTCG_REQUEST_DELAY_SECONDS)
    url = f"{root}{path}"
    try:
        response = requests.post(url, json=payload, headers=_headers(), timeout=60)
        if response.status_code == 429:
            retry = response.headers.get("Retry-After")
            LOG.warning("JustTCG 429 (Retry-After=%s) — raising", retry or "?")
            raise JustTCGRateLimitError(response=response)
        response.raise_for_status()
        data = response.json()
    except JustTCGRateLimitError:
        raise
    except Exception as exc:
        _note_justtcg_failure(exc)
        raise
    _note_justtcg_success()
    if len(_POST_CACHE) >= _POST_CACHE_MAX:
        _POST_CACHE.pop(next(iter(_POST_CACHE)), None)
    _POST_CACHE[key] = data
    return data


def _post_v2(path: str, payload: Any) -> dict[str, Any]:
    return _post(path, payload, base_url=JUSTTCG_API_V2_BASE_URL)


def _get_v2_page(
    path: str,
    params: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str | None]:
    """GET /v2/… bypassing response cache so Link ``rel=next`` cursor stays accurate."""
    _consume_request_budget()
    sleep(JUSTTCG_REQUEST_DELAY_SECONDS)
    url = f"{JUSTTCG_API_V2_BASE_URL.rstrip('/')}{path}"
    try:
        response = requests.get(url, params=params or {}, headers=_headers(), timeout=45)
        if response.status_code == 429:
            retry = response.headers.get("Retry-After")
            LOG.warning("JustTCG 429 (Retry-After=%s) — raising", retry or "?")
            raise JustTCGRateLimitError(response=response)
        response.raise_for_status()
        payload = response.json()
    except JustTCGRateLimitError:
        raise
    except Exception as exc:
        _note_justtcg_failure(exc)
        raise
    if not isinstance(payload, dict):
        _note_justtcg_failure(RuntimeError("JustTCG unexpected payload shape"))
        raise RuntimeError("JustTCG unexpected payload shape")
    _note_justtcg_success()
    return payload, _parse_next_cursor(response.headers.get("Link"))


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


# Soft Ink lot labels → JustTCG API condition / printing strings.
CONDITION_TO_JUSTTCG: dict[str, str] = {
    "NM": "Near Mint",
    "LP": "Lightly Played",
    "MP": "Moderately Played",
    "HP": "Heavily Played",
    "DMG": "Damaged",
}
PRINTING_TO_JUSTTCG: dict[str, str] = {
    "Normal": "Normal",
    "Reverse": "Reverse Holofoil",
    "Holo": "Holofoil",
}


def _variant_condition(v: dict[str, Any]) -> str:
    return str(v.get("condition") or "").strip().lower()


def _variant_printing(v: dict[str, Any]) -> str:
    return str(v.get("printing") or "").strip().lower()


def _variant_has_price(v: dict[str, Any]) -> bool:
    return variant_price_usd(v) is not None


def _condition_matches(raw: str, wanted: str) -> bool:
    text = (raw or "").strip().lower()
    key = (wanted or "").strip().lower()
    if not text or not key:
        return False
    aliases = {
        "nm": ("near mint", "nm", "near_mint"),
        "near mint": ("near mint", "nm", "near_mint"),
        "lp": ("lightly played", "lp", "lightly_played"),
        "lightly played": ("lightly played", "lp", "lightly_played"),
        "mp": ("moderately played", "mp", "moderately_played"),
        "moderately played": ("moderately played", "mp", "moderately_played"),
        "hp": ("heavily played", "hp", "heavily_played"),
        "heavily played": ("heavily played", "hp", "heavily_played"),
        "dmg": ("damaged", "dmg"),
        "damaged": ("damaged", "dmg"),
    }
    needles = aliases.get(key, (key,))
    return any(n in text or text == n for n in needles)


def _printing_matches(raw: str, wanted: str) -> bool:
    text = (raw or "").strip().lower()
    key = (wanted or "").strip().lower()
    if not text or not key:
        return False
    if key in {"normal", "nonfoil", "non-foil"}:
        return "normal" in text or text in {"normal", "nonfoil", "non-foil"}
    if key in {"reverse", "reverse holo", "reverse holofoil"}:
        return "reverse" in text
    if key in {"holo", "holofoil", "foil"}:
        return ("holo" in text or "foil" in text) and "reverse" not in text
    return key in text or text == key


def _is_graded_variant(variant: dict[str, Any]) -> bool:
    if str(variant.get("type") or "").lower() == "graded":
        return True
    cond = _variant_condition(variant)
    return cond.startswith("psa") or cond.startswith("cgc") or cond.startswith("bgs")


def _raw_variants(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw = [v for v in variants if not _is_graded_variant(v)]
    return raw or list(variants)


def pick_nm_variant(variants: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Preferiraj Near Mint Holofoil, zatim NM bilo koji printing, zatim prva s cijenom."""
    if not variants:
        return None

    pool_src = _raw_variants(variants)
    nm = [
        v
        for v in pool_src
        if _condition_matches(_variant_condition(v), "Near Mint")
    ]
    pool = nm or pool_src
    for preferred in ("holofoil", "holo", "reverse holofoil", "reverse holo", "normal"):
        for variant in pool:
            if preferred in _variant_printing(variant) and _variant_has_price(variant):
                return variant
    for variant in pool:
        if _variant_has_price(variant):
            return variant
    return pool[0] if pool else None


def pick_variant(
    variants: list[dict[str, Any]],
    *,
    condition: str = "NM",
    printing: str = "Normal",
) -> dict[str, Any] | None:
    """Pick the JustTCG variant matching Soft Ink condition + printing labels."""
    if not variants:
        return None
    from services.lot_price_adjust import normalize_condition, normalize_printing

    cond = normalize_condition(condition)
    print_ = normalize_printing(printing)
    wanted_cond = CONDITION_TO_JUSTTCG.get(cond, "Near Mint")
    wanted_print = PRINTING_TO_JUSTTCG.get(print_, "Normal")
    pool = _raw_variants(variants)

    matched = [
        v
        for v in pool
        if _condition_matches(_variant_condition(v), wanted_cond)
        and _printing_matches(_variant_printing(v), wanted_print)
    ]
    for variant in matched:
        if _variant_has_price(variant):
            return variant
    if matched:
        return matched[0]

    # Soft fallback: same condition, any printing with a price.
    same_cond = [
        v for v in pool if _condition_matches(_variant_condition(v), wanted_cond)
    ]
    for variant in same_cond:
        if _variant_has_price(variant):
            return variant
    return None


def card_tcgplayer_id(card: dict[str, Any] | None) -> str | None:
    """TCGPlayer product id from v2 ``tcgplayer_id`` / ``external_ids`` or v1 camelCase."""
    if not card:
        return None
    for key in ("tcgplayer_id", "tcgplayerId"):
        raw = card.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    external = card.get("external_ids")
    if isinstance(external, dict):
        raw = external.get("tcgplayer") or external.get("tcgplayer_id")
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


def _prefer_na_market(variant: dict[str, Any] | None) -> dict[str, Any] | None:
    """v2 ``markets[]`` entry for NA (or first priced); None when absent (v1 flat)."""
    if not variant:
        return None
    markets = variant.get("markets")
    if not isinstance(markets, list) or not markets:
        return None
    for region in (JUSTTCG_REGION, "US", "USA"):
        for market in markets:
            if (
                isinstance(market, dict)
                and str(market.get("region") or "").upper() == region
            ):
                return market
    for market in markets:
        if isinstance(market, dict):
            return market
    return None


def variant_price_usd(variant: dict[str, Any] | None) -> float | None:
    """Effective USD spot — v2 markets[] first, then v1 flat priceStatus fields."""
    if not variant:
        return None

    def _pos(raw: Any) -> float | None:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    market = _prefer_na_market(variant)
    source = market if market is not None else variant
    status = str(
        source.get("price_status")
        or source.get("priceStatus")
        or ""
    ).strip().lower()
    price = _pos(source.get("price"))
    last = _pos(
        source.get("last_price")
        or source.get("lastKnownPrice")
        or variant.get("lastKnownPrice")
        or variant.get("last_price")
    )
    if price is not None:
        return price
    if status == "unpriced":
        return None
    if last is not None and status in {"", "expired"}:
        return last
    if last is not None:
        return last
    return None


def _history_list_from_variant(variant: dict[str, Any]) -> list[Any]:
    market = _prefer_na_market(variant)
    if market is not None:
        for key in ("price_history", "priceHistory"):
            raw = market.get(key)
            if isinstance(raw, list) and raw:
                return raw
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
    """Jedna karta po TCGplayer product id via GET /v2/cards (empty data = not found)."""
    tid = str(tcgplayer_id or "").strip()
    if not tid:
        return None

    # Soft Ink detail remounts: GET hits the in-process cache.
    # Do not POST-fallback on empty data[] — same id will not appear in batch.
    payload = _get_v2(
        "/cards",
        _v2_raw_params(
            tcgplayer_id=tid,
            condition="NM",
            limit=5,
        ),
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


def _search_cards_raw(
    q: str,
    *,
    limit: int = 20,
    number: str | None = None,
) -> list[dict[str, Any]]:
    query = (q or "").strip()
    if not query:
        return []
    # Plan max cards/request (Free 20 … Pro 100) — clamp to JUSTTCG_BATCH_SIZE.
    safe_limit = max(1, min(int(limit), JUSTTCG_BATCH_SIZE))
    # v2: game id ``pokemon``; ``query`` + optional ``number``; graded=exclude.
    params = _v2_raw_params(
        game=JUSTTCG_GAME,
        query=query,
        condition="NM",
        limit=safe_limit,
    )
    num = normalize_card_number(number) if number else ""
    if num and num != "0":
        params["number"] = num
    payload = _get_v2("/cards", params)
    return list(payload.get("data") or [])


def search_pokemon_card(
    *,
    name: str,
    number: str | None = None,
    set_name: str | None = None,
    quick: bool = False,
) -> dict[str, Any] | None:
    """Pronađi JustTCG kartu — preferiraj name+number (set u queryu često pokvari match).

    quick=True: only the first (most precise) query — for backfill under rate limits.
    """
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
    if quick:
        queries = queries[:1]

    best: dict[str, Any] | None = None
    best_score = -1
    seen_q: set[str] = set()
    for q in queries:
        key = q.lower()
        if not q or key in seen_q:
            continue
        seen_q.add(key)
        try:
            rows = _search_cards_raw(
                q,
                limit=JUSTTCG_BATCH_SIZE,
                number=wanted_number or None,
            )
        except JustTCGRateLimitError:
            raise
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
    resolved = card_tcgplayer_id(card) or resolved
    variant = pick_nm_variant(list(card.get("variants") or []))
    points = history_points_from_variant(variant)
    # If the top match has no series, try other strong number matches via a fresh number query.
    if not points and number:
        try:
            rows = _search_cards_raw(
                f"{name} {normalize_card_number(number)}".strip(),
                limit=JUSTTCG_BATCH_SIZE,
                number=normalize_card_number(number),
            )
            wanted = normalize_card_number(number)
            for row in rows:
                if not _card_number_matches(row.get("number"), wanted):
                    continue
                variant = pick_nm_variant(list(row.get("variants") or []))
                points = history_points_from_variant(variant)
                if points:
                    resolved = card_tcgplayer_id(row) or resolved
                    break
        except Exception as exc:
            LOG.warning("JustTCG number retry failed: %s", exc)
    return points, resolved


def list_pokemon_sets() -> list[dict[str, Any]]:
    payload = _get("/sets", {"game": JUSTTCG_GAME})
    return list(payload.get("data") or [])


def _normalize_set_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def set_code_variants(set_code: str | None) -> set[str]:
    """pokemontcg codes often omit zero-padding (swsh7 vs JustTCG swsh07)."""
    raw = (set_code or "").strip().lower()
    if not raw:
        return set()
    out = {raw, _normalize_set_token(raw)}
    match = re.match(r"^([a-z]+)(\d+)([a-z0-9]*)$", raw)
    if match:
        prefix, digits, suffix = match.groups()
        out.add(f"{prefix}{digits.zfill(2)}{suffix}")
        out.add(f"{prefix}{str(int(digits))}{suffix}")
        out.add(_normalize_set_token(f"{prefix}{digits.zfill(2)}{suffix}"))
    return {v for v in out if v}


def _row_set_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or "").strip()


def _row_set_name(row: dict[str, Any]) -> str:
    return str(row.get("name") or "").strip()


def score_justtcg_set_row(
    row: dict[str, Any],
    *,
    wanted_name: str,
    set_code: str | None = None,
) -> int | None:
    """Confidence score for a JustTCG /sets row, or None if it must not be used.

    Never treat "first row in the list" as a match — that caused mass
    resolves to alternate-art-promos-pokemon.
    """
    sid = _row_set_id(row)
    name = _row_set_name(row)
    if not sid:
        return None
    wanted = (wanted_name or "").strip().lower()
    name_l = name.lower()
    sid_l = sid.lower()

    if wanted and name_l == wanted:
        return 100
    if wanted and sid_l == wanted:
        return 100
    if wanted and _normalize_set_token(name) == _normalize_set_token(wanted):
        return 95

    code_hits = set_code_variants(set_code)
    if code_hits:
        tokens = {t for t in re.split(r"[^a-z0-9]+", sid_l) if t}
        tokens |= {_normalize_set_token(sid_l)}
        if code_hits & tokens:
            return 80
        for code in code_hits:
            if sid_l.startswith(f"{code}-") or f"-{code}-" in f"-{sid_l}-":
                return 75

    if wanted and wanted in name_l and len(wanted) >= 4:
        return 40
    return None


def pick_justtcg_set_id(
    rows: list[dict[str, Any]],
    *,
    set_name: str,
    set_code: str | None = None,
) -> str | None:
    """Pick best JustTCG set id from candidate rows; None if no confident match."""
    best_id: str | None = None
    best_score = -1
    for row in rows:
        score = score_justtcg_set_row(
            row, wanted_name=set_name, set_code=set_code
        )
        if score is None:
            continue
        if score > best_score:
            best_score = score
            best_id = _row_set_id(row)
    # Require at least a code-token or exact-ish name match.
    if best_score < 75:
        return None
    return best_id or None


def resolve_set_id(
    set_name: str,
    *,
    set_code: str | None = None,
    cache: dict[str, str] | None = None,
    catalog_rows: list[dict[str, Any]] | None = None,
) -> str | None:
    """Map our set name/code (e.g. '151' / 'sv3pt5') to a JustTCG set id.

    Returns None when no confident match exists — never falls back to rows[0].

    Pass ``catalog_rows`` (from one ``list_pokemon_sets()`` call) to match
    locally and avoid a 6s+ network round-trip per set. Nightly used to burn
    hours resolving unmatched sets one query at a time.
    """
    wanted = (set_name or "").strip()
    code = (set_code or "").strip() or None
    if not wanted and not code:
        return None
    cache_key = f"{wanted.lower()}|{code or ''}".lower()
    if cache is not None and cache_key in cache:
        hit = cache[cache_key]
        return hit or None

    label = wanted or (code or "")

    # Prefer one-shot catalog match — no per-set /sets?q= delay.
    if catalog_rows is not None:
        set_id = pick_justtcg_set_id(catalog_rows, set_name=label, set_code=code)
        if cache is not None:
            cache[cache_key] = set_id or ""
        return set_id

    queries: list[str] = []
    for q in (wanted, code):
        if q and q not in queries:
            queries.append(q)

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for q in queries:
        try:
            payload = _get("/sets", {"game": JUSTTCG_GAME, "q": q})
        except Exception as exc:
            LOG.warning("JustTCG set query %r failed: %s", q, exc)
            continue
        for row in list(payload.get("data") or []):
            sid = _row_set_id(row)
            if not sid or sid in seen_ids:
                continue
            seen_ids.add(sid)
            rows.append(row)

    if not rows:
        try:
            rows = list_pokemon_sets()
        except Exception as exc:
            LOG.warning("JustTCG list_pokemon_sets failed: %s", exc)
            rows = []

    set_id = pick_justtcg_set_id(rows, set_name=label, set_code=code)
    if cache is not None:
        cache[cache_key] = set_id or ""
    return set_id


def fetch_set_cards_page(
    set_id: str,
    *,
    cursor: str | None = None,
    offset: int = 0,
    limit: int = JUSTTCG_BATCH_SIZE,
) -> tuple[list[dict[str, Any]], str | None]:
    """One /v2/cards page for a set. Returns ``(rows, next_cursor)``.

    v2 dropped ``offset`` — pass ``cursor`` from the previous page's Link header.
    ``offset`` is accepted for call-site compatibility but ignored.
    """
    del offset  # v2 has no offset pagination
    params = _v2_raw_params(
        game=JUSTTCG_GAME,
        set=set_id,
        condition="NM",
        limit=min(int(limit), JUSTTCG_BATCH_SIZE),
    )
    if cursor:
        params["cursor"] = str(cursor)
    payload, next_cursor = _get_v2_page("/cards", params)
    rows = list(payload.get("data") or [])
    return rows, next_cursor


def batch_by_tcgplayer_ids(tcgplayer_ids: list[str]) -> list[dict[str, Any]]:
    """POST /v2/cards batch NM lookup with history (nightly sync)."""
    if not tcgplayer_ids:
        return []
    # v2 batch body is snake_case; abbreviated conditions (NM / LP).
    body = [
        {"tcgplayer_id": str(tid), "condition": "NM"}
        for tid in tcgplayer_ids[:JUSTTCG_BATCH_SIZE]
    ]
    payload = _post_v2(_v2_batch_path(history=True), body)
    return list(payload.get("data") or [])


def batch_variant_lookups(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """POST /v2/cards batch with per-item condition + printing (max JUSTTCG_BATCH_SIZE).

    Spot-only include (periods, no price_history) — Soft Ink portfolio/trade.
    Each item: {tcgplayerId, condition?, printing?} using Soft Ink or JustTCG labels.
    """
    if not items:
        return []
    from services.lot_price_adjust import normalize_condition, normalize_printing

    body: list[dict[str, str]] = []
    for raw in items[:JUSTTCG_BATCH_SIZE]:
        tid = str(raw.get("tcgplayerId") or raw.get("tcgplayer_id") or "").strip()
        if not tid:
            continue
        cond = normalize_condition(raw.get("condition") or "NM")
        print_ = normalize_printing(raw.get("printing") or "Normal")
        body.append(
            {
                "tcgplayer_id": tid,
                "condition": cond if cond in CONDITION_TO_JUSTTCG else "NM",
                "printing": PRINTING_TO_JUSTTCG.get(print_, "Normal"),
            }
        )
    if not body:
        return []
    payload = _post_v2(_v2_batch_path(history=False), body)
    return list(payload.get("data") or [])




def __getattr__(name: str):
    """Lazy PSA10 re-exports — avoids circular import with justtcg_psa10."""
    _psa10_names = {
        "fetch_psa10_card_by_tcgplayer_id",
        "fetch_psa_card_by_tcgplayer_id",
        "history_points_from_v2_variant",
        "pick_psa10_variant",
        "pick_psa9_variant",
        "pick_psa_variant",
        "psa10_history_for_card",
        "psa9_history_for_card",
        "psa_histories_for_card",
        "psa_history_for_card",
        "psa10_stats_from_variant",
        "psa_stats_from_variant",
        "search_psa10_pokemon_card",
        "search_psa_pokemon_card",
    }
    if name not in _psa10_names:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import justtcg_psa10 as _psa10

    value = getattr(_psa10, name)
    globals()[name] = value
    return value

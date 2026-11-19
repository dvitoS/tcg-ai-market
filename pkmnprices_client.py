"""PkmnPrices API client — NM prices + history (parallel to JustTCG).

Auth: ``X-API-Key: $PKMN_API_KEY`` (Render / Actions secret name).
Docs: https://www.pkmnprices.com/docs
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from time import sleep
from typing import Any

import requests

from config import PKMN_API_BASE_URL, PKMN_API_KEY, PKMN_REQUEST_DELAY_SECONDS, _secret

LOG = logging.getLogger("tcg.pkmnprices")

_GET_CACHE: dict[str, dict[str, Any]] = {}
_GET_CACHE_MAX = 128
_REQUEST_COUNT = 0


class PkmnPricesError(RuntimeError):
    def __init__(self, message: str, *, response: requests.Response | None = None):
        super().__init__(message)
        self.response = response


class PkmnPricesRateLimitError(PkmnPricesError):
    pass


def clear_pkmnprices_cache() -> None:
    _GET_CACHE.clear()


def pkmnprices_request_count() -> int:
    return int(_REQUEST_COUNT)


def reset_pkmnprices_request_count() -> None:
    global _REQUEST_COUNT
    _REQUEST_COUNT = 0


def pkmn_api_key() -> str:
    """Fresh key — prefer ``PKMN_API_KEY`` (Render), accept SDK-style alias."""
    try:
        from config import get_pkmn_api_key

        return get_pkmn_api_key()
    except Exception:
        return (_secret("PKMN_API_KEY") or PKMN_API_KEY or "").strip()


def pkmnprices_configured() -> bool:
    return bool(pkmn_api_key())


def _headers() -> dict[str, str]:
    key = pkmn_api_key()
    if not key:
        raise PkmnPricesError(
            "PKMN_API_KEY nije postavljen. Dodaj ga u Render / .env / Actions secrets."
        )
    return {
        "X-API-Key": key,
        "Accept": "application/json",
        "User-Agent": "kestrel-tcg/1.0 (+https://www.kestreltcg.app)",
    }


def _cache_key(path: str, params: dict[str, Any] | None) -> str:
    items = tuple(sorted((params or {}).items()))
    return f"{path}|{items}"


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    global _REQUEST_COUNT
    root = (PKMN_API_BASE_URL or "https://api.pkmnprices.com").rstrip("/")
    url = f"{root}{path if path.startswith('/') else '/' + path}"
    key = _cache_key(path, params)
    cached = _GET_CACHE.get(key)
    if cached is not None:
        return cached

    if PKMN_REQUEST_DELAY_SECONDS > 0 and _REQUEST_COUNT > 0:
        sleep(float(PKMN_REQUEST_DELAY_SECONDS))

    _REQUEST_COUNT += 1
    try:
        res = requests.get(url, headers=_headers(), params=params or {}, timeout=30)
    except requests.RequestException as exc:
        raise PkmnPricesError(f"PkmnPrices network error: {exc}") from exc

    if res.status_code == 429:
        raise PkmnPricesRateLimitError(
            "PkmnPrices rate/credit limit exceeded",
            response=res,
        )
    if res.status_code == 401:
        raise PkmnPricesError("PkmnPrices unauthorized — check PKMN_API_KEY", response=res)
    if res.status_code == 403:
        raise PkmnPricesError(
            "PkmnPrices forbidden — plan may lack this endpoint",
            response=res,
        )
    if res.status_code >= 400:
        raise PkmnPricesError(
            f"PkmnPrices HTTP {res.status_code}: {(res.text or '')[:180]}",
            response=res,
        )

    try:
        payload = res.json()
    except ValueError as exc:
        raise PkmnPricesError("PkmnPrices returned non-JSON", response=res) from exc
    if not isinstance(payload, dict):
        raise PkmnPricesError("PkmnPrices JSON root must be an object", response=res)

    if len(_GET_CACHE) >= _GET_CACHE_MAX and key not in _GET_CACHE:
        oldest = next(iter(_GET_CACHE), None)
        if oldest is not None:
            _GET_CACHE.pop(oldest, None)
    _GET_CACHE[key] = payload
    return payload


def find_card_id_by_tcgplayer_id(tcgplayer_id: str | int | None) -> int | None:
    """Resolve Soft Ink / TCP product id → PkmnPrices integer card id."""
    if tcgplayer_id is None:
        return None
    raw = str(tcgplayer_id).strip()
    if not raw.isdigit():
        return None
    payload = _get("/v1/cards", {"tcg_player_id": int(raw), "per_page": 1})
    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    if not rows:
        return None
    try:
        return int(rows[0].get("id"))
    except (TypeError, ValueError):
        return None


def get_card(card_id: int, *, currency: str = "usd") -> dict[str, Any]:
    return _get(f"/v1/cards/{int(card_id)}", {"currency": currency})


def _nm_usd_price(card_payload: dict[str, Any]) -> float | None:
    prices = card_payload.get("prices")
    if not isinstance(prices, list):
        return None
    nm_rows: list[tuple[float, float]] = []
    for row in prices:
        if not isinstance(row, dict):
            continue
        if str(row.get("currency") or "").upper() not in {"USD", ""}:
            if str(row.get("source") or "").lower() != "tcgplayer":
                continue
        if str(row.get("condition") or "") != "Near Mint":
            continue
        try:
            price = float(row.get("market_price"))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        # Prefer Holofoil / Normal over obscure variants when several NM rows exist.
        variant = str(row.get("variant") or "").lower()
        rank = 0.0
        if "holo" in variant and "reverse" not in variant:
            rank = 2.0
        elif variant in {"normal", "holofoil", ""}:
            rank = 1.0
        nm_rows.append((rank, price))
    if not nm_rows:
        return None
    nm_rows.sort(key=lambda t: t[0], reverse=True)
    return float(nm_rows[0][1])


def nm_spot_for_tcgplayer_id(tcgplayer_id: str | int | None) -> float | None:
    """Current TCGPlayer Near Mint market price via PkmnPrices."""
    pid = find_card_id_by_tcgplayer_id(tcgplayer_id)
    if pid is None:
        return None
    card = get_card(pid, currency="usd")
    return _nm_usd_price(card)


def _parse_history_date(raw: Any) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return None


def nm_history_for_tcgplayer_id(
    tcgplayer_id: str | int | None,
    *,
    period: str = "90d",
    limit: int = 120,
) -> list[dict[str, Any]]:
    """Daily TCGPlayer Near Mint closes → Soft Ink ``[{date, price}, ...]``.

    Credits: 1 per history row returned — keep ``limit`` modest.
    """
    pid = find_card_id_by_tcgplayer_id(tcgplayer_id)
    if pid is None:
        return []

    per_page = max(1, min(365, int(limit)))
    payload = _get(
        f"/v1/cards/{int(pid)}/prices/history",
        {
            "currency": "usd",
            "period": period,
            "condition": "Near Mint",
            "limit": per_page,
            "page": 1,
        },
    )
    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("source") or "").lower() not in {"tcgplayer", ""}:
            continue
        if str(row.get("condition") or "") not in {"Near Mint", ""}:
            continue
        day = _parse_history_date(row.get("date"))
        if not day:
            continue
        price_raw = row.get("avg")
        if price_raw is None:
            price_raw = row.get("market_price") or row.get("price")
        try:
            price = float(price_raw)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        out.append({"date": day, "price": price})

    # Newest last — match JustTCG Soft Ink series shape.
    out.sort(key=lambda r: r["date"])
    # Collapse same-day multi-variant rows to the last (prefer later variant order).
    by_day: dict[str, float] = {}
    for row in out:
        by_day[row["date"]] = float(row["price"])
    return [{"date": d, "price": by_day[d]} for d in sorted(by_day)]


def psa_ebay_comps_for_tcgplayer_id(
    tcgplayer_id: str | int | None,
    *,
    grade: float | int = 10,
    period: str = "90d",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """PSA eBay sold comps (Pro+/Scale). 1 credit per row returned (max 20/page)."""
    pid = find_card_id_by_tcgplayer_id(tcgplayer_id)
    if pid is None:
        return []
    grade_s = str(int(grade) if float(grade).is_integer() else grade)
    payload = _get(
        f"/v1/cards/{int(pid)}/listings/ebay",
        {
            "graded": "true",
            "grader": "PSA",
            "grade": grade_s,
            "period": period,
            "sort": "date_asc",
            "limit": max(1, min(20, int(limit))),
        },
    )
    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("grader") or "").upper() != "PSA":
            continue
        if str(row.get("grade") or "") != grade_s:
            continue
        if str(row.get("currency") or "USD").upper() not in {"USD", ""}:
            continue
        day = _parse_history_date(row.get("sold_at") or row.get("date"))
        if not day:
            continue
        try:
            price = float(row.get("price"))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        out.append(
            {
                "date": day,
                "price": price,
                "title": str(row.get("title") or ""),
                "listing_url": str(row.get("listing_url") or ""),
            }
        )
    out.sort(key=lambda r: r["date"])
    return out


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def psa_series_from_comps(comps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Daily median of eBay comps → Soft Ink ``[{date, price}, ...]``."""
    by_day: dict[str, list[float]] = {}
    for row in comps:
        day = str(row.get("date") or "").strip()
        if not day:
            continue
        try:
            price = float(row["price"])
        except (TypeError, ValueError, KeyError):
            continue
        if price <= 0:
            continue
        by_day.setdefault(day, []).append(price)
    return [{"date": d, "price": _median(by_day[d])} for d in sorted(by_day)]


def psa_history_for_tcgplayer_id(
    tcgplayer_id: str | int | None,
    *,
    grade: float | int = 10,
    period: str = "90d",
    limit: int = 20,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """PSA grade series synthesized from eBay sold comps + Soft Ink stats blob."""
    comps = psa_ebay_comps_for_tcgplayer_id(
        tcgplayer_id,
        grade=grade,
        period=period,
        limit=limit,
    )
    points = psa_series_from_comps(comps)
    tip = float(points[-1]["price"]) if points else None
    grade_label = int(grade) if float(grade).is_integer() else grade
    stats: dict[str, Any] = {
        "price": tip,
        "currency": "USD",
        "price_status": "ebay_comps",
        "period_key": period,
        "sales_count": len(comps),
        "has_history_series": bool(points),
        "canonical": f"PSA {grade_label}",
        "last_sale_at": None,
        "price_expires_at": None,
        "source": "pkmnprices",
    }
    return points, stats

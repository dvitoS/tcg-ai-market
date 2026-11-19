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


# Soft Ink lot labels → PkmnPrices card.prices[] strings (TCGPlayer schema).
CONDITION_TO_PKMN: dict[str, str] = {
    "NM": "Near Mint",
    "LP": "Lightly Played",
    "MP": "Moderately Played",
    "HP": "Heavily Played",
    "DMG": "Damaged",
}
PRINTING_TO_PKMN: dict[str, str] = {
    "Normal": "Normal",
    "Reverse": "Reverse Holofoil",
    "Holo": "Holofoil",
}


def _is_usd_tcgplayer_row(row: dict[str, Any]) -> bool:
    currency = str(row.get("currency") or "").upper()
    source = str(row.get("source") or "").lower()
    if currency in {"USD", ""}:
        return source in {"tcgplayer", ""}
    return source == "tcgplayer"


def _printing_matches_pkmn(api_variant: str, wanted: str) -> bool:
    a = str(api_variant or "").strip().lower()
    w = str(wanted or "").strip().lower()
    if a == w:
        return True
    if "reverse" in w:
        return "reverse" in a
    if w in {"holofoil", "holo"}:
        return "holo" in a and "reverse" not in a
    if w == "normal":
        return a in {"normal", ""}
    return False


def _pick_usd_price_row(
    prices: list[Any],
    *,
    condition: str = "NM",
    printing: str = "Normal",
) -> dict[str, Any] | None:
    """Pick market_price row matching Soft Ink condition + printing."""
    from services.lot_price_adjust import normalize_condition, normalize_printing

    cond = normalize_condition(condition)
    print_ = normalize_printing(printing)
    wanted_cond = CONDITION_TO_PKMN.get(cond, "Near Mint")
    wanted_print = PRINTING_TO_PKMN.get(print_, "Normal")

    pool: list[dict[str, Any]] = []
    for row in prices:
        if not isinstance(row, dict):
            continue
        if not _is_usd_tcgplayer_row(row):
            continue
        try:
            price = float(row.get("market_price"))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        pool.append(row)

    exact = [
        r
        for r in pool
        if str(r.get("condition") or "") == wanted_cond
        and _printing_matches_pkmn(str(r.get("variant") or ""), wanted_print)
    ]
    if exact:
        return exact[0]

    # Soft fallback: same condition, any printing (prefer Normal then Holo).
    same_cond = [r for r in pool if str(r.get("condition") or "") == wanted_cond]
    if not same_cond:
        return None

    def _rank(row: dict[str, Any]) -> float:
        variant = str(row.get("variant") or "").lower()
        if variant in {"normal", ""}:
            return 3.0
        if "holo" in variant and "reverse" not in variant:
            return 2.0
        if "reverse" in variant:
            return 1.0
        return 0.0

    same_cond.sort(key=_rank, reverse=True)
    return same_cond[0]


def _nm_usd_price(card_payload: dict[str, Any]) -> float | None:
    prices = card_payload.get("prices")
    if not isinstance(prices, list):
        return None
    # Prefer Holofoil over Normal for default NM board tip (legacy behavior).
    holo = _pick_usd_price_row(prices, condition="NM", printing="Holo")
    if holo is not None:
        try:
            return float(holo["market_price"])
        except (TypeError, ValueError, KeyError):
            pass
    normal = _pick_usd_price_row(prices, condition="NM", printing="Normal")
    if normal is None:
        return None
    try:
        return float(normal["market_price"])
    except (TypeError, ValueError, KeyError):
        return None


def nm_spot_for_tcgplayer_id(tcgplayer_id: str | int | None) -> float | None:
    """Current TCGPlayer Near Mint market price via PkmnPrices."""
    pid = find_card_id_by_tcgplayer_id(tcgplayer_id)
    if pid is None:
        return None
    card = get_card(pid, currency="usd")
    return _nm_usd_price(card)


def variant_spot_for_tcgplayer_id(
    tcgplayer_id: str | int | None,
    *,
    condition: str = "NM",
    printing: str = "Normal",
) -> dict[str, Any] | None:
    """Live condition×printing market price from PkmnPrices card.prices[].

    Returns ``{price, tcgplayer_id, condition, variant, pkmn_card_id}`` or None.
    """
    if tcgplayer_id is None:
        return None
    tcp = str(tcgplayer_id).strip()
    if not tcp:
        return None
    pid = find_card_id_by_tcgplayer_id(tcp)
    if pid is None:
        return None
    card = get_card(pid, currency="usd")
    prices = card.get("prices") if isinstance(card, dict) else None
    if not isinstance(prices, list):
        return None
    row = _pick_usd_price_row(prices, condition=condition, printing=printing)
    if row is None:
        return None
    try:
        price = float(row["market_price"])
    except (TypeError, ValueError, KeyError):
        return None
    return {
        "price": price,
        "tcgplayer_id": tcp,
        "condition": str(row.get("condition") or ""),
        "variant": str(row.get("variant") or ""),
        "pkmn_card_id": int(pid),
    }


def batch_variant_spots(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Resolve many Soft Ink condition/printing spots with one get_card per TCP.

    Each item: ``{tcgplayerId|tcgplayer_id, condition, printing}``.
    Returns ``tcp|CONDITION|PRINTING`` → variant_spot payload (+ ``source``).
    """
    from services.lot_price_adjust import normalize_condition, normalize_printing

    out: dict[str, dict[str, Any]] = {}
    if not items or not pkmnprices_configured():
        return out

    by_tcp: dict[str, list[dict[str, Any]]] = {}
    for raw in items:
        tcp = str(
            raw.get("tcgplayerId") or raw.get("tcgplayer_id") or ""
        ).strip()
        if not tcp:
            continue
        cond = normalize_condition(raw.get("condition") or "NM")
        print_ = normalize_printing(raw.get("printing") or "Normal")
        by_tcp.setdefault(tcp, []).append(
            {"condition": cond, "printing": print_}
        )

    for tcp, reqs in by_tcp.items():
        try:
            pid = find_card_id_by_tcgplayer_id(tcp)
        except PkmnPricesRateLimitError:
            raise
        except Exception as exc:
            LOG.info("pkmn variant tcp lookup %s: %s", tcp, exc)
            continue
        if pid is None:
            continue
        try:
            card = get_card(pid, currency="usd")
        except PkmnPricesRateLimitError:
            raise
        except Exception as exc:
            LOG.info("pkmn variant get_card %s: %s", tcp, exc)
            continue
        prices = card.get("prices") if isinstance(card, dict) else None
        if not isinstance(prices, list):
            continue
        seen: set[str] = set()
        for req in reqs:
            key = f"{tcp}|{req['condition']}|{req['printing']}"
            if key in seen:
                continue
            seen.add(key)
            row = _pick_usd_price_row(
                prices,
                condition=req["condition"],
                printing=req["printing"],
            )
            if row is None:
                continue
            try:
                price = float(row["market_price"])
            except (TypeError, ValueError, KeyError):
                continue
            out[key] = {
                "price": price,
                "tcgplayer_id": tcp,
                "condition": str(row.get("condition") or ""),
                "variant": str(row.get("variant") or ""),
                "pkmn_card_id": int(pid),
                "source": "pkmnprices_variant",
            }
    return out


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
    currency: str = "usd",
) -> list[dict[str, Any]]:
    """Daily Near Mint closes → Soft Ink ``[{date, price}, ...]``.

    ``currency=usd`` → TCGplayer (USD). ``currency=eur`` → Cardmarket (EUR).
    Credits: 1 per history row returned — keep ``limit`` modest.
    """
    pid = find_card_id_by_tcgplayer_id(tcgplayer_id)
    if pid is None:
        return []

    cur = str(currency or "usd").strip().lower()
    if cur not in {"usd", "eur"}:
        cur = "usd"
    source_want = "cardmarket" if cur == "eur" else "tcgplayer"

    per_page = max(1, min(365, int(limit)))
    payload = _get(
        f"/v1/cards/{int(pid)}/prices/history",
        {
            "currency": cur,
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
        src = str(row.get("source") or "").lower()
        if src and src not in {source_want, ""}:
            continue
        row_cur = str(row.get("currency") or "").upper()
        if cur == "eur" and row_cur and row_cur not in {"EUR", ""}:
            continue
        if cur == "usd" and row_cur and row_cur not in {"USD", ""}:
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


def ebay_sold_search_url(
    *,
    title: str | None = None,
    listing_url: str | None = None,
) -> str | None:
    """Outbound link for a *sold* comp — never raw /itm alone.

    Ended eBay /itm/ pages often redirect to similar *active* listings with a
    different ask, so Soft Ink prices look "wrong". Prefer Completed+Sold
    search keyed by title (or item id) so the click stays in sold results.
    """
    from urllib.parse import quote_plus, urlsplit

    title_s = str(title or "").strip()
    raw = str(listing_url or "").strip()
    item_id: str | None = None
    if raw:
        path = urlsplit(raw).path or ""
        # /itm/123456789012 or /itm/some-slug/123456789012
        parts = [p for p in path.split("/") if p]
        for part in reversed(parts):
            digits = "".join(ch for ch in part if ch.isdigit())
            if len(digits) >= 9:
                item_id = digits
                break

    query = title_s[:140] if title_s else (item_id or "")
    if not query:
        return None
    return (
        "https://www.ebay.com/sch/i.html"
        f"?_nkw={quote_plus(query)}"
        "&LH_Sold=1&LH_Complete=1&rt=nc&_sop=13"
    )


def ebay_sold_listings_for_tcgplayer_id(
    tcgplayer_id: str | int | None,
    *,
    graded: bool | None = False,
    period: str = "90d",
    limit: int = 12,
    exact_attribution_only: bool = True,
) -> list[dict[str, Any]]:
    """Recent eBay sold comps (raw by default). 1 credit/row (max 20/page).

    Drops ``attribution=shared`` by default (same sale mirrored onto sibling
    printings — title/price often describe the other card). Outbound ``url`` is
    a Completed+Sold search, not a live /itm ask page.
    """
    pid = find_card_id_by_tcgplayer_id(tcgplayer_id)
    if pid is None:
        return []
    # Fetch a little extra so shared/unknown drops still leave ``limit`` rows.
    fetch_n = max(1, min(20, int(limit) * 2 if exact_attribution_only else int(limit)))
    params: dict[str, Any] = {
        "period": period,
        "sort": "date_desc",
        "limit": fetch_n,
    }
    if graded is True:
        params["graded"] = "true"
    elif graded is False:
        params["graded"] = "false"
    try:
        payload = _get(f"/v1/cards/{int(pid)}/listings/ebay", params)
    except PkmnPricesError as exc:
        res = getattr(exc, "response", None)
        if res is not None and getattr(res, "status_code", None) == 403:
            return []
        raise
    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        attr = str(row.get("attribution") or "").strip().lower()
        if exact_attribution_only and attr == "shared":
            continue
        # Must be a dated sale — undated rows are not trustworthy sold comps.
        day = _parse_history_date(row.get("sold_at") or row.get("date"))
        if not day:
            continue
        try:
            price = float(row.get("price"))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        currency = str(row.get("currency") or "USD").upper() or "USD"
        title = str(row.get("title") or "").strip() or None
        listing_url = (
            str(row.get("listing_url") or row.get("url") or "").strip() or None
        )
        out.append(
            {
                "price": price,
                "currency": currency,
                "date": day,
                "title": title,
                "url": ebay_sold_search_url(title=title, listing_url=listing_url),
                "condition": str(row.get("condition") or "").strip() or None,
                "graded": bool(row.get("graded")),
                "grader": str(row.get("grader") or "").strip() or None,
                "grade": str(row.get("grade") or "").strip() or None,
                "sale_type": str(row.get("sale_type") or "").strip() or None,
                "variant": str(row.get("variant") or "").strip() or None,
                "seller_country": str(row.get("seller_country") or "").strip()
                or None,
                "attribution": attr or None,
            }
        )
        if len(out) >= max(1, min(20, int(limit))):
            break
    return out


def cardmarket_offers_for_tcgplayer_id(
    tcgplayer_id: str | int | None,
    *,
    condition: str = "Near Mint",
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Live Cardmarket raw offers (EUR). 1 credit/row (max 20/page)."""
    pid = find_card_id_by_tcgplayer_id(tcgplayer_id)
    if pid is None:
        return []
    params: dict[str, Any] = {
        "graded": "false",
        "signed": "false",
        "altered": "false",
        "sort": "price_asc",
        "limit": max(1, min(20, int(limit))),
    }
    if condition:
        params["condition"] = condition
    try:
        payload = _get(f"/v1/cards/{int(pid)}/listings/cardmarket", params)
    except PkmnPricesError as exc:
        res = getattr(exc, "response", None)
        if res is not None and getattr(res, "status_code", None) == 403:
            return []
        raise
    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        # Defense in depth — never treat signed/altered/graded as raw NM.
        if row.get("signed") or row.get("altered") or row.get("graded"):
            continue
        try:
            price = float(row.get("price"))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        out.append(
            {
                "price": price,
                "currency": "EUR",
                "condition": str(row.get("condition") or "").strip() or None,
                "variant": str(row.get("variant") or "").strip() or None,
                "seller": str(row.get("seller") or "").strip() or None,
                "seller_country": str(row.get("seller_country") or "").strip()
                or None,
                "sell_count": row.get("sell_count"),
                "language": str(row.get("language") or "").strip() or None,
                "quantity": row.get("quantity"),
            }
        )
    return out


def _is_near_mint_condition(value: str | None) -> bool:
    raw = str(value or "").strip().lower()
    if not raw:
        return False
    if raw in {"nm", "near mint", "mint"}:
        return True
    return raw.startswith("near mint")


def tcgplayer_offers_for_tcgplayer_id(
    tcgplayer_id: str | int | None,
    *,
    condition: str = "Near Mint",
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Live TCGplayer marketplace offers (USD). 1 credit/row (max 20/page).

    Sorted by ``total_asc`` (price + shipping) to match TCGplayer's own list.
    These are current asks — not sold comps (eBay covers solds).

    Raises ``PkmnPricesError`` when the TCP id cannot be resolved in PkmnPrices
    or the plan forbids listings (403) — Soft Ink must not pretend that is an
    empty marketplace.
    """
    tcp_s = str(tcgplayer_id or "").strip()
    if not tcp_s.isdigit():
        raise PkmnPricesError(f"Invalid tcgplayer_id={tcp_s!r}")
    pid = find_card_id_by_tcgplayer_id(tcp_s)
    if pid is None:
        raise PkmnPricesError(
            f"PkmnPrices has no card for tcgplayer_id={tcp_s}"
        )
    product_url = f"https://www.tcgplayer.com/product/{tcp_s}"
    limit_n = max(1, min(20, int(limit)))
    wanted = str(condition or "").strip()

    def _map_rows(rows: list[Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                price = float(row.get("price"))
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            try:
                ship = float(row.get("shipping_price") or 0)
            except (TypeError, ValueError):
                ship = 0.0
            if ship < 0:
                ship = 0.0
            out.append(
                {
                    "price": price,
                    "shipping_price": ship,
                    "currency": "USD",
                    "condition": str(row.get("condition") or "").strip() or None,
                    "variant": str(row.get("printing") or "").strip() or None,
                    "seller": str(row.get("seller_name") or "").strip() or None,
                    "language": str(row.get("language") or "").strip() or None,
                    "quantity": row.get("quantity"),
                    "url": product_url,
                    "title": str(row.get("custom_title") or "").strip() or None,
                }
            )
        return out

    def _load(extra: dict[str, Any]) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "sort": "total_asc",
            "limit": limit_n,
            **extra,
        }
        payload = _get(f"/v1/cards/{int(pid)}/listings/tcgplayer", params)
        rows = payload.get("data") if isinstance(payload.get("data"), list) else []
        return _map_rows(rows)

    # Prefer NM+English, then relax filters — Pkmn snapshots are EN-first but
    # condition/language params can over-filter vs TCGplayer.com.
    attempts: list[dict[str, Any]] = []
    if wanted:
        attempts.extend(
            [
                {"condition": wanted, "language": "English"},
                {"condition": wanted},
                {"language": "English"},
                {},
            ]
        )
    else:
        attempts.extend([{"language": "English"}, {}])

    seen: set[tuple[tuple[str, Any], ...]] = set()
    broadened: list[dict[str, Any]] = []
    for extra in attempts:
        key = tuple(sorted(extra.items()))
        if key in seen:
            continue
        seen.add(key)
        rows = _load(extra)
        if not rows:
            continue
        if wanted:
            nm = [r for r in rows if _is_near_mint_condition(r.get("condition"))]
            if nm:
                return nm
            if "condition" in extra:
                # API already filtered by condition — trust that set.
                return rows
            # Keep non-NM as last resort after all NM-preferring attempts.
            if not broadened:
                broadened = rows
            continue
        return rows
    return broadened


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


def _population_variant_rank(variant: str) -> float:
    text = str(variant or "").strip().lower()
    if "holo" in text and "reverse" not in text:
        return 3.0
    if text in {"normal", ""}:
        return 2.0
    if "reverse" in text:
        return 1.0
    return 0.0


def _grade_count(grades: Any, key: str) -> int | None:
    if not isinstance(grades, dict):
        return None
    raw = grades.get(key)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _summarize_population_variant(row: dict[str, Any]) -> dict[str, Any]:
    """Collapse one PkmnPrices population variant into Soft Ink grading EV fields."""
    grades = row.get("grades") if isinstance(row.get("grades"), dict) else {}
    percent_higher = (
        row.get("percent_higher")
        if isinstance(row.get("percent_higher"), dict)
        else {}
    )
    graders = row.get("graders") if isinstance(row.get("graders"), dict) else {}
    psa = graders.get("PSA") if isinstance(graders.get("PSA"), dict) else {}
    psa_grades = psa.get("grades") if isinstance(psa.get("grades"), dict) else {}

    def _pct(raw: Any) -> float | None:
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    psa_gem = _pct(psa.get("gem_rate"))
    overall_gem = _pct(row.get("gem_rate"))
    # Prefer PSA gem rate for the "PSA 10 hit %" slider; fall back to overall.
    gem_for_ev = psa_gem if psa_gem is not None else overall_gem

    pop_url = None
    if psa.get("pop_report_url"):
        pop_url = str(psa.get("pop_report_url")).strip() or None

    def _int(raw: Any) -> int | None:
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    # Compact grade ladder for Soft Ink detail table (PkmnPrices-style).
    grade_rows: list[dict[str, Any]] = []
    total_pop = _int(row.get("total_population")) or 0
    for key in ("10", "9.5", "9", "8.5", "8", "7.5", "7"):
        count = _grade_count(grades, key)
        if count is None or count <= 0:
            continue
        share = (100.0 * count / total_pop) if total_pop > 0 else None
        grade_rows.append(
            {
                "grade": key,
                "count": count,
                "share_pct": share,
                "percent_higher": _pct(percent_higher.get(key)),
            }
        )
    below = 0
    for gkey, gval in grades.items():
        try:
            if float(gkey) < 7:
                below += int(gval)
        except (TypeError, ValueError):
            continue
    if below > 0:
        grade_rows.append(
            {
                "grade": "below_7",
                "count": below,
                "share_pct": (100.0 * below / total_pop) if total_pop > 0 else None,
                "percent_higher": _pct(percent_higher.get("7")),
            }
        )

    return {
        "source": "pkmnprices",
        "variant": str(row.get("variant") or "").strip() or None,
        "total_population": _int(row.get("total_population")),
        "total_gems": _int(row.get("total_gems")),
        "gem_rate": overall_gem,
        "psa_total": _int(psa.get("total")),
        "psa_10": _grade_count(psa_grades, "10"),
        "psa_9": _grade_count(psa_grades, "9"),
        "psa_gem_rate": psa_gem,
        "gem_rate_for_ev": gem_for_ev,
        "percent_higher_9": _pct(percent_higher.get("9")),
        "grades_10": _grade_count(grades, "10"),
        "grades_9": _grade_count(grades, "9"),
        "grade_rows": grade_rows,
        "pop_report_url": pop_url,
        "updated_at": str(row.get("updated_at") or "").strip() or None,
        "last_population_change": str(row.get("last_population_change") or "").strip()
        or None,
    }


def population_for_tcgplayer_id(
    tcgplayer_id: str | int | None,
    *,
    variant: str | None = None,
) -> dict[str, Any] | None:
    """Graded population summary for Soft Ink Grading EV (Pro+; 1 credit).

    Picks Holofoil when several printings exist (unless ``variant`` is set).
    Returns None on empty / unmatched / Free-plan 403.
    """
    pid = find_card_id_by_tcgplayer_id(tcgplayer_id)
    if pid is None:
        return None
    params: dict[str, Any] = {}
    if variant and str(variant).strip():
        params["variant"] = str(variant).strip()
    try:
        payload = _get(f"/v1/cards/{int(pid)}/population", params or None)
    except PkmnPricesError as exc:
        # Free plan → 403; treat as soft miss so EV still works on comps alone.
        res = getattr(exc, "response", None)
        if res is not None and getattr(res, "status_code", None) == 403:
            LOG.info("PkmnPrices population forbidden (plan) for tcp=%s", tcgplayer_id)
            return None
        raise
    rows = payload.get("variants") if isinstance(payload.get("variants"), list) else []
    candidates = [r for r in rows if isinstance(r, dict)]
    if not candidates:
        return None
    candidates.sort(
        key=lambda r: (
            _population_variant_rank(str(r.get("variant") or "")),
            int(r.get("total_population") or 0),
        ),
        reverse=True,
    )
    summary = _summarize_population_variant(candidates[0])
    summary["pkmn_card_id"] = int(pid)
    summary["tcgplayer_id"] = str(tcgplayer_id).strip()
    return summary


def find_sealed_id_by_tcgplayer_id(tcgplayer_id: str | int | None) -> int | None:
    """Resolve TCP product id → PkmnPrices sealed integer id (list has no prices)."""
    if tcgplayer_id is None:
        return None
    raw = str(tcgplayer_id).strip()
    if not raw.isdigit():
        return None
    payload = _get("/v1/sealed", {"tcg_player_id": int(raw), "per_page": 1})
    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    if not rows:
        return None
    try:
        return int(rows[0].get("id"))
    except (TypeError, ValueError):
        return None


def get_sealed(sealed_id: int, *, currency: str = "usd") -> dict[str, Any]:
    return _get(f"/v1/sealed/{int(sealed_id)}", {"currency": currency})


def _sealed_usd_spot(payload: dict[str, Any]) -> float | None:
    prices = payload.get("prices")
    if not isinstance(prices, list):
        return None
    for row in prices:
        if not isinstance(row, dict):
            continue
        if str(row.get("currency") or "").upper() not in {"USD", ""}:
            continue
        if str(row.get("source") or "").lower() not in {"tcgplayer", ""}:
            continue
        try:
            price = float(row.get("market_price"))
        except (TypeError, ValueError):
            continue
        if price > 0:
            return price
    return None


def sealed_spot_for_tcgplayer_id(tcgplayer_id: str | int | None) -> float | None:
    """Current TCGPlayer sealed market price via PkmnPrices."""
    sid = find_sealed_id_by_tcgplayer_id(tcgplayer_id)
    if sid is None:
        return None
    return _sealed_usd_spot(get_sealed(sid, currency="usd"))


def _sealed_hit_from_payload(payload: dict[str, Any], *, tcp_fallback: str | None = None) -> dict[str, Any] | None:
    spot = _sealed_usd_spot(payload)
    if spot is None:
        return None
    tcp_raw = payload.get("tcg_player_id")
    if tcp_raw is None:
        tcp_raw = tcp_fallback
    tcp = str(tcp_raw or "").strip()
    if not tcp.isdigit():
        # Soft Ink card_id needs a stable handle — prefer TCP; else Pkmn sealed id.
        sid = payload.get("id")
        if sid is None:
            return None
        tcp = f"pkmn{int(sid)}"
    set_obj = payload.get("set") if isinstance(payload.get("set"), dict) else {}
    set_name = str(set_obj.get("name") or "").strip() or None
    name = str(payload.get("name") or "").strip() or f"Sealed {tcp}"
    image = str(payload.get("image_url") or "").strip() or None
    return {
        "card_id": f"sealed:{tcp}",
        "name": name,
        "set_name": set_name,
        "tcgplayer_id": tcp if tcp.isdigit() else None,
        "gtin": None,
        "spot_usd": float(spot),
        "image_url": image,
        "source": "pkmnprices",
        "kind": "sealed",
    }


def sealed_quote_for_tcgplayer_id(tcgplayer_id: str | int | None) -> dict[str, Any] | None:
    """Normalized Soft Ink sealed hit (same shape as ``justtcg_sealed.normalize_sealed_hit``)."""
    if tcgplayer_id is None:
        return None
    tcp = str(tcgplayer_id).strip()
    if not tcp.isdigit():
        return None
    sid = find_sealed_id_by_tcgplayer_id(tcp)
    if sid is None:
        return None
    return _sealed_hit_from_payload(get_sealed(sid, currency="usd"), tcp_fallback=tcp)


def search_sealed_by_name(name: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """Name search → Soft Ink sealed hits (list + per-id spot fetch).

    List endpoint has no prices (1 credit/row); each detail is +1 credit.
    Cap ``limit`` modestly for Soft Ink desk search.
    """
    q = str(name or "").strip()
    if len(q) < 2:
        return []
    per_page = max(1, min(20, int(limit)))
    payload = _get("/v1/sealed", {"name": q, "per_page": per_page, "page": 1})
    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            sid = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        try:
            detail = get_sealed(sid, currency="usd")
        except Exception:
            continue
        # Prefer list image/name if detail omits them.
        if not detail.get("image_url") and row.get("image_url"):
            detail = {**detail, "image_url": row.get("image_url")}
        if not detail.get("name") and row.get("name"):
            detail = {**detail, "name": row.get("name")}
        if not detail.get("tcg_player_id") and row.get("tcg_player_id") is not None:
            detail = {**detail, "tcg_player_id": row.get("tcg_player_id")}
        if not detail.get("set") and isinstance(row.get("set"), dict):
            detail = {**detail, "set": row.get("set")}
        hit = _sealed_hit_from_payload(detail)
        if not hit:
            continue
        cid = str(hit["card_id"])
        if cid in seen:
            continue
        seen.add(cid)
        out.append(hit)
        if len(out) >= per_page:
            break
    return out

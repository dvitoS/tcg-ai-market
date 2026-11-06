"""JustTCG PSA graded helpers (PSA 10 / PSA 9) — /v2/cards graded shape.

Aligned with https://justtcg.com/docs/api/cards-v2/graded and thin-markets expiry:
- graded variants live in the same ``variants`` array (``type=graded`` + ``grading``)
- request with ``grading_company=PSA`` + ``grade`` as a string list (e.g. ``9,10``)
- ``graded=only`` is free of the include surcharge; company alone also forces only
- prices are sales-backed: ``null`` until first sale, expire 90d after last sale
- when ``price_status=expired``, read ``last_price``; ``unpriced`` means never sold
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

LOG = logging.getLogger("tcg.justtcg")

# Narrow periods + history windows (docs: include=periods.Xd narrows response).
JUSTTCG_PSA10_HISTORY_INCLUDE = "periods.30d,periods.90d,periods.1y,price_history.90d"
JUSTTCG_PSA_HISTORY_INCLUDE = JUSTTCG_PSA10_HISTORY_INCLUDE


def _client():
    import justtcg_client as jtcg

    return jtcg


def _grade_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_grade_param(grades: list[float]) -> str:
    """Docs: grade is string[] — encode as comma-separated (e.g. ``9,10``)."""
    parts: list[str] = []
    for grade in grades:
        g = float(grade)
        parts.append(str(int(g)) if g.is_integer() else str(g))
    return ",".join(parts)


def pick_psa_variant(
    variants: list[dict[str, Any]],
    *,
    grade: float = 10.0,
) -> dict[str, Any] | None:
    """Best PSA graded variant for ``grade`` (prefer no qualifier + priced)."""
    target = float(grade)
    graded: list[dict[str, Any]] = []
    for variant in variants or []:
        if str(variant.get("type") or "").lower() != "graded":
            continue
        grading = variant.get("grading") or {}
        company = str(grading.get("company") or "").upper()
        g = _grade_float(grading.get("grade"))
        if company != "PSA" or g is None or abs(g - target) > 1e-6:
            continue
        graded.append(variant)
    if not graded:
        return None

    def _rank(v: dict[str, Any]) -> tuple[int, int, int]:
        grading = v.get("grading") or {}
        has_qual = 1 if grading.get("qualifier") else 0
        status = _market_price_status(v)
        # Prefer current → expired (last_price) → unpriced.
        status_rank = {"current": 0, "expired": 1}.get(status, 2)
        priced = 0 if _market_price_usd(v) is None else -1
        return (has_qual, status_rank, priced)

    graded.sort(key=_rank)
    return graded[0]


def pick_psa10_variant(variants: list[dict[str, Any]]) -> dict[str, Any] | None:
    return pick_psa_variant(variants, grade=10.0)


def pick_psa9_variant(variants: list[dict[str, Any]]) -> dict[str, Any] | None:
    return pick_psa_variant(variants, grade=9.0)


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


def _as_positive_float(raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _market_price_status(variant: dict[str, Any] | None) -> str:
    market = _prefer_na_market(_market_entries(variant)) or {}
    status = str(market.get("price_status") or "").strip().lower()
    if status in {"current", "expired", "unpriced"}:
        return status
    if _as_positive_float(market.get("price")) is not None:
        return "current"
    if _as_positive_float(market.get("last_price")) is not None:
        return "expired"
    return "unpriced"


def _market_price_usd(variant: dict[str, Any] | None) -> float | None:
    """Effective USD spot: current ``price``, else expired ``last_price``."""
    market = _prefer_na_market(_market_entries(variant))
    if not market:
        return _client().variant_price_usd(variant)
    price = _as_positive_float(market.get("price"))
    if price is not None:
        return price
    status = str(market.get("price_status") or "").strip().lower()
    last = _as_positive_float(market.get("last_price"))
    if last is not None and status in {"", "expired"}:
        return last
    # Some payloads omit price_status but still carry last_price after expiry.
    if price is None and last is not None and status != "unpriced":
        return last
    return _client().variant_price_usd(variant)


def history_points_from_v2_variant(variant: dict[str, Any] | None) -> list[dict[str, Any]]:
    """v2 markets[].price_history [{t,p}] → [{date, price}]; spot/last_price fallback."""
    if not variant:
        return []
    market = _prefer_na_market(_market_entries(variant))
    if not market:
        return _client().history_points_from_variant(variant)

    synthetic = {
        "price": market.get("price"),
        "lastKnownPrice": market.get("last_price"),
        "price_history": market.get("price_history") or market.get("priceHistory") or [],
    }
    points = _client().history_points_from_variant(synthetic)
    if points:
        return points
    spot = _market_price_usd(variant)
    if spot is None:
        return []
    return [{"date": date.today(), "price": round(spot, 4)}]


def psa_stats_from_variant(
    variant: dict[str, Any] | None,
    *,
    canonical: str = "PSA 10",
) -> dict[str, Any]:
    """Agregati iz markets[].periods + price_status / sale timestamps."""
    market = _prefer_na_market(_market_entries(variant)) or {}
    periods = market.get("periods") if isinstance(market.get("periods"), dict) else {}
    window = None
    # Prefer 90d for graded (docs: sales_count rests on 90d window).
    for key in ("90d", "30d", "1y", "7d", "all_time"):
        if key in periods and isinstance(periods[key], dict):
            window = key
            break
    stats = dict(periods.get(window) or {}) if window else {}
    status = _market_price_status(variant)
    return {
        "price": _market_price_usd(variant),
        "currency": str(market.get("currency") or "USD"),
        "price_status": status,
        "updated_at": market.get("updated_at"),
        "last_sale_at": market.get("last_sale_at"),
        "price_expires_at": market.get("price_expires_at"),
        "period_key": window,
        "sales_count": stats.get("sales_count"),
        "avg": stats.get("avg"),
        "min": stats.get("min"),
        "max": stats.get("max"),
        "change_pct": stats.get("change_pct"),
        "canonical": ((variant or {}).get("grading") or {}).get("canonical") or canonical,
        "has_history_series": bool(
            (market.get("price_history") or market.get("priceHistory") or [])
        ),
    }


def psa10_stats_from_variant(variant: dict[str, Any] | None) -> dict[str, Any]:
    return psa_stats_from_variant(variant, canonical="PSA 10")


def _graded_card_params(*, grades: list[float]) -> dict[str, Any]:
    """Shared /v2/cards graded query — company implies graded=only (docs)."""
    return {
        # Explicit only keeps cost at base rate (include would surcharge at GA).
        "graded": "only",
        "grading_company": "PSA",
        "grade": _format_grade_param(grades),
        "include": JUSTTCG_PSA_HISTORY_INCLUDE,
        "regions": "NA",
    }


def fetch_psa_card_by_tcgplayer_id(
    tcgplayer_id: str,
    *,
    grade: float = 10.0,
    grades: list[float] | None = None,
) -> dict[str, Any] | None:
    """GET /v2/cards — one card by TCGplayer id with PSA grade filter(s)."""
    tid = str(tcgplayer_id or "").strip()
    if not tid:
        return None
    wanted = list(grades) if grades else [float(grade)]
    params = {
        "tcgplayer_id": tid,
        **_graded_card_params(grades=wanted),
        "limit": 5,
    }
    payload = _client()._get_v2("/cards", params)
    rows = list(payload.get("data") or [])
    return rows[0] if rows else None


def fetch_psa10_card_by_tcgplayer_id(tcgplayer_id: str) -> dict[str, Any] | None:
    return fetch_psa_card_by_tcgplayer_id(tcgplayer_id, grade=10.0)


def search_psa_pokemon_card(
    *,
    name: str,
    number: str | None = None,
    set_name: str | None = None,
    grade: float = 10.0,
    grades: list[float] | None = None,
) -> dict[str, Any] | None:
    """Search /v2/cards for PSA grade(s) — fallback when tcgplayer_id is unknown."""
    query = " ".join(part for part in (name, number) if part).strip()
    if not query:
        return None
    q = f"{query} {set_name}".strip() if set_name else query
    wanted = list(grades) if grades else [float(grade)]
    jtcg = _client()
    payload = jtcg._get_v2(
        "/cards",
        {
            "game": "pokemon",
            "q": q,
            **_graded_card_params(grades=wanted),
            "limit": 20,
        },
    )
    rows = list(payload.get("data") or [])
    if not rows:
        return None
    wanted_number = jtcg.normalize_card_number(number) if number else ""
    if wanted_number:
        for row in rows:
            if jtcg.normalize_card_number(str(row.get("number") or "")) == wanted_number:
                return row
    wanted_name = (name or "").strip().lower()
    exact = next(
        (r for r in rows if str(r.get("name") or "").strip().lower() == wanted_name),
        None,
    )
    return exact or rows[0]


def search_psa10_pokemon_card(
    *,
    name: str,
    number: str | None = None,
    set_name: str | None = None,
) -> dict[str, Any] | None:
    return search_psa_pokemon_card(
        name=name, number=number, set_name=set_name, grade=10.0
    )


def _resolve_card_for_grades(
    *,
    grades: list[float],
    tcgplayer_id: str | None,
    name: str | None,
    number: str | None,
    set_name: str | None,
) -> tuple[dict[str, Any] | None, str | None, bool]:
    """Return (card, resolved_tcp, used_tcp_lookup).

    When a TCGplayer lookup returns a card, do **not** burn a second search call —
    missing/unpriced PSA prints are a coverage signal, not a wrong id.
    """
    resolved: str | None = str(tcgplayer_id).strip() if tcgplayer_id else None
    if resolved:
        card = fetch_psa_card_by_tcgplayer_id(resolved, grades=grades)
        if card is not None:
            return card, resolved, True
        # Empty data[] for a known product id → no graded rows / no match; skip search.
        return None, resolved, True
    card = search_psa_pokemon_card(
        name=str(name or ""),
        number=number,
        set_name=set_name,
        grades=grades,
    )
    return card, resolved, False


def _points_and_stats_for_grade(
    card: dict[str, Any],
    *,
    grade: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    variant = pick_psa_variant(list(card.get("variants") or []), grade=grade)
    if not variant:
        return [], {}
    # Unpriced slab (never sold) — keep stats for UI, no fake chart points.
    if _market_price_status(variant) == "unpriced" and _market_price_usd(variant) is None:
        canonical = f"PSA {int(grade) if float(grade).is_integer() else grade}"
        return [], psa_stats_from_variant(variant, canonical=canonical)
    points = history_points_from_v2_variant(variant)
    canonical = f"PSA {int(grade) if float(grade).is_integer() else grade}"
    stats = psa_stats_from_variant(variant, canonical=canonical)
    return points, stats


def psa_histories_for_card(
    *,
    grades: list[float] | None = None,
    tcgplayer_id: str | None = None,
    name: str | None = None,
    number: str | None = None,
    set_name: str | None = None,
) -> tuple[dict[float, tuple[list[dict[str, Any]], dict[str, Any]]], str | None]:
    """One JustTCG call for one or more PSA grades.

    Returns ``({grade: (points, stats)}, resolved_tcgplayer_id)``.
    Prefer this over separate PSA9 + PSA10 calls to cut quota burn.
    """
    wanted = [float(g) for g in (grades or [10.0])]
    if not wanted:
        wanted = [10.0]
    card, resolved, _ = _resolve_card_for_grades(
        grades=wanted,
        tcgplayer_id=tcgplayer_id,
        name=name,
        number=number,
        set_name=set_name,
    )
    if not card:
        return {g: ([], {}) for g in wanted}, resolved

    external = card.get("external_ids") if isinstance(card.get("external_ids"), dict) else {}
    resolved = (
        str(external.get("tcgplayer") or card.get("tcgplayerId") or resolved or "")
        or resolved
    )
    out: dict[float, tuple[list[dict[str, Any]], dict[str, Any]]] = {}
    for grade in wanted:
        out[grade] = _points_and_stats_for_grade(card, grade=grade)
    return out, resolved


def psa_history_for_card(
    *,
    grade: float = 10.0,
    tcgplayer_id: str | None = None,
    name: str | None = None,
    number: str | None = None,
    set_name: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any]]:
    """(points, resolved_tcgplayer_id, stats) for a single PSA grade."""
    bundle, resolved = psa_histories_for_card(
        grades=[float(grade)],
        tcgplayer_id=tcgplayer_id,
        name=name,
        number=number,
        set_name=set_name,
    )
    points, stats = bundle.get(float(grade), ([], {}))
    return points, resolved, stats


def psa10_history_for_card(
    *,
    tcgplayer_id: str | None = None,
    name: str | None = None,
    number: str | None = None,
    set_name: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any]]:
    return psa_history_for_card(
        grade=10.0,
        tcgplayer_id=tcgplayer_id,
        name=name,
        number=number,
        set_name=set_name,
    )


def psa9_history_for_card(
    *,
    tcgplayer_id: str | None = None,
    name: str | None = None,
    number: str | None = None,
    set_name: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any]]:
    return psa_history_for_card(
        grade=9.0,
        tcgplayer_id=tcgplayer_id,
        name=name,
        number=number,
        set_name=set_name,
    )

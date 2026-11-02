"""JustTCG PSA 10 / v2 graded helpers."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from justtcg_client import (
    JUSTTCG_PSA10_HISTORY_INCLUDE,
    _get_v2,
    normalize_card_number,
)

LOG = logging.getLogger("tcg.justtcg")

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

"""PkmnPrices market comps for Soft Ink detail — eBay sold, Cardmarket, population."""

from __future__ import annotations

import logging
from typing import Any

LOG = logging.getLogger("tcg.market_comps")


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def _card_number_from_id(card_id: str) -> str | None:
    if "-" not in str(card_id):
        return None
    return str(card_id).rsplit("-", 1)[-1].strip() or None


def _resolve_tcp(card_id: str) -> tuple[str | None, str, str | None]:
    """Return (tcp, name, set_name) from board / DB, then Path-B TCGplayer search."""
    name = str(card_id)
    set_name: str | None = None
    tcp: str | None = None
    try:
        from api.catalog_service import load_board

        board, _ = load_board()
        if board is not None and not board.empty:
            hits = board[board["id"].astype(str) == str(card_id)]
            if not hits.empty:
                row = hits.iloc[0]
                name = str(row.get("name") or card_id)
                set_name = str(row.get("set_name") or "") or None
                raw_tcp = row.get("tcgplayer_id")
                if raw_tcp is not None and str(raw_tcp).strip():
                    tcp = str(raw_tcp).strip()
    except Exception as exc:
        LOG.info("market_comps board lookup failed for %s: %s", card_id, exc)
    if not tcp:
        try:
            from database import get_card

            card = get_card(str(card_id))
            if card is not None:
                name = str(getattr(card, "name", None) or name)
                set_name = str(getattr(card, "set_name", None) or "") or set_name
                raw = getattr(card, "tcgplayer_id", None)
                if raw is not None and str(raw).strip():
                    tcp = str(raw).strip()
        except Exception as exc:
            LOG.info("market_comps db lookup failed for %s: %s", card_id, exc)
    if tcp:
        return tcp, name, set_name

    # Path B — TCGplayer storefront search (no JustTCG / Pkmn quota).
    try:
        from backfill_tcgplayer_ids import resolve_tcgplayer_id_from_search
        from database import update_card_tcgplayer_id

        search_name = name if name and name != str(card_id) else ""
        if not search_name:
            return tcp, name, set_name
        tid, score = resolve_tcgplayer_id_from_search(
            name=search_name,
            number=_card_number_from_id(str(card_id)),
            set_name=set_name,
            min_score=120,
        )
        if tid:
            tcp = str(tid).strip()
            try:
                update_card_tcgplayer_id(str(card_id), tcp)
            except Exception as exc:
                LOG.info("market_comps tcp persist failed for %s: %s", card_id, exc)
            LOG.info(
                "market_comps Path-B tcp=%s score=%s for %s",
                tcp,
                score,
                card_id,
            )
    except Exception as exc:
        LOG.info("market_comps Path-B resolve failed for %s: %s", card_id, exc)
    return tcp, name, set_name


def build_market_comps(card_id: str, *, limit: int = 10) -> dict[str, Any]:
    """Bundle eBay sold + Cardmarket offers + graded population for one card."""
    from pkmnprices_client import (
        PkmnPricesRateLimitError,
        cardmarket_offers_for_tcgplayer_id,
        ebay_sold_listings_for_tcgplayer_id,
        pkmnprices_configured,
        population_for_tcgplayer_id,
    )

    tcp, name, set_name = _resolve_tcp(str(card_id))
    limit = max(1, min(20, int(limit or 10)))
    payload: dict[str, Any] = {
        "card_id": str(card_id),
        "name": name,
        "set_name": set_name,
        "tcgplayer_id": tcp,
        "pkmnprices_configured": bool(pkmnprices_configured()),
        "ebay_sold": [],
        "ebay_sold_stats": {},
        "ebay_error": None,
        "cardmarket": [],
        "cardmarket_stats": {},
        "cardmarket_error": None,
        "population": None,
        "population_error": None,
    }
    if not pkmnprices_configured():
        payload["ebay_error"] = "PKMN_API_KEY not configured"
        payload["cardmarket_error"] = "PKMN_API_KEY not configured"
        payload["population_error"] = "PKMN_API_KEY not configured"
        return payload
    if not tcp:
        payload["ebay_error"] = "No tcgplayer_id for this card"
        payload["cardmarket_error"] = "No tcgplayer_id for this card"
        payload["population_error"] = "No tcgplayer_id for this card"
        return payload

    try:
        sold = ebay_sold_listings_for_tcgplayer_id(
            tcp, graded=False, period="90d", limit=limit
        )
        try:
            from services.epn import tag_listing_urls

            sold = tag_listing_urls(
                sold, customid=f"detail-sold-{card_id}"
            )
        except Exception:
            pass
        prices = [float(r["price"]) for r in sold if r.get("currency") == "USD"]
        payload["ebay_sold"] = sold
        payload["ebay_sold_stats"] = {
            "n": len(sold),
            "median": _median(prices),
            "low": min(prices) if prices else None,
            "high": max(prices) if prices else None,
            "currency": "USD",
            "period": "90d",
            "is_sold": True,
        }
    except PkmnPricesRateLimitError:
        payload["ebay_error"] = "PkmnPrices rate/credit limited — try again later."
    except Exception as exc:
        payload["ebay_error"] = str(exc)[:180]
        LOG.info("market_comps ebay failed for %s: %s", card_id, exc)

    try:
        offers = cardmarket_offers_for_tcgplayer_id(
            tcp, condition="Near Mint", limit=limit
        )
        eur = [float(r["price"]) for r in offers]
        payload["cardmarket"] = offers
        payload["cardmarket_stats"] = {
            "n": len(offers),
            "lowest": min(eur) if eur else None,
            "currency": "EUR",
            "condition": "Near Mint",
        }
    except PkmnPricesRateLimitError:
        payload["cardmarket_error"] = (
            "PkmnPrices rate/credit limited — try again later."
        )
    except Exception as exc:
        payload["cardmarket_error"] = str(exc)[:180]
        LOG.info("market_comps cardmarket failed for %s: %s", card_id, exc)

    try:
        pop = population_for_tcgplayer_id(tcp)
        payload["population"] = pop
    except PkmnPricesRateLimitError:
        payload["population_error"] = (
            "PkmnPrices rate/credit limited — try again later."
        )
    except Exception as exc:
        payload["population_error"] = str(exc)[:180]
        LOG.info("market_comps population failed for %s: %s", card_id, exc)

    return payload

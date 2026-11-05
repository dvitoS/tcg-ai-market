"""Sealed product quotes + catalog ensure for portfolio MTM."""

from __future__ import annotations

import logging
from typing import Any

from api.demo_mode import demo_mode

LOG = logging.getLogger("kestrel.api.sealed")

# Demo / no-key fallbacks — illustrative Soft Ink seed (not live quotes).
_DEMO_SEALED: list[dict[str, Any]] = [
    {
        "card_id": "sealed:demo-surging-etb",
        "name": "Surging Sparks Elite Trainer Box",
        "set_name": "Surging Sparks",
        "tcgplayer_id": "demo-surging-etb",
        "gtin": None,
        "spot_usd": 49.99,
        "image_url": None,
        "source": "demo",
        "kind": "sealed",
    },
    {
        "card_id": "sealed:demo-prism-box",
        "name": "Prismatic Evolutions Booster Bundle",
        "set_name": "Prismatic Evolutions",
        "tcgplayer_id": "demo-prism-box",
        "gtin": None,
        "spot_usd": 64.5,
        "image_url": None,
        "source": "demo",
        "kind": "sealed",
    },
    {
        "card_id": "sealed:demo-151-upc",
        "name": "Scarlet & Violet—151 Ultra-Premium Collection",
        "set_name": "151",
        "tcgplayer_id": "demo-151-upc",
        "gtin": None,
        "spot_usd": 129.99,
        "image_url": None,
        "source": "demo",
        "kind": "sealed",
    },
]


def _filter_demo(q: str | None) -> list[dict[str, Any]]:
    text = (q or "").strip().lower()
    if not text:
        return list(_DEMO_SEALED)
    return [
        row
        for row in _DEMO_SEALED
        if text in str(row["name"]).lower()
        or text in str(row.get("set_name") or "").lower()
        or text in str(row.get("tcgplayer_id") or "").lower()
    ]


def quote_sealed_products(
    *,
    q: str | None = None,
    tcgplayer_id: str | None = None,
    gtin: str | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    from justtcg_client import justtcg_api_key

    limit = max(1, min(int(limit or 8), 20))
    has_key = bool(justtcg_api_key())
    if not has_key or demo_mode():
        hits = _filter_demo(q or tcgplayer_id or gtin)
        return {
            "items": hits[:limit],
            "source": "demo",
            "justtcg_configured": has_key,
        }

    try:
        from justtcg_sealed import quote_sealed

        items = quote_sealed(
            q=q,
            tcgplayer_id=tcgplayer_id,
            gtin=gtin,
            limit=limit,
        )
        return {
            "items": items[:limit],
            "source": "justtcg" if items else "empty",
            "justtcg_configured": True,
        }
    except Exception as exc:
        LOG.info("sealed quote failed: %s", exc)
        return {
            "items": [],
            "source": "empty",
            "justtcg_configured": True,
            "error": str(exc)[:180],
        }


def ensure_sealed_card(hit: dict[str, Any]) -> dict[str, Any]:
    """Upsert a synthetic cards row so portfolio FK / MTM join works."""
    card_id = str(hit.get("card_id") or "").strip()
    if not card_id.startswith("sealed:"):
        raise ValueError("Not a sealed card_id.")
    name = str(hit.get("name") or "").strip() or card_id
    spot = hit.get("spot_usd")
    try:
        market = float(spot) if spot is not None else None
    except (TypeError, ValueError):
        market = None
    row = {
        "id": card_id,
        "name": name,
        "supertype": "Sealed",
        "rarity": "Sealed",
        "set_name": hit.get("set_name"),
        "market_price": market,
        "pokewallet_id": None,
        "tcgplayer_id": hit.get("tcgplayer_id"),
        "image_url": hit.get("image_url"),
    }
    if demo_mode():
        return {**hit, "ensured": True, "demo": True}

    from database import upsert_cards

    upsert_cards([row])
    return {**hit, "ensured": True, "demo": False}

"""Sealed product quotes + catalog ensure for portfolio MTM."""

from __future__ import annotations

import logging
from typing import Any

from api.demo_mode import demo_mode

LOG = logging.getLogger("kestrel.api.sealed")

# Demo / no-key Soft Ink showcase — real TCGPlayer ids so CDN art works.
# Spots are illustrative until JustTCG is queried live.
_DEMO_SEALED: list[dict[str, Any]] = [
    {
        "card_id": "sealed:565630",
        "name": "Surging Sparks Elite Trainer Box (ETB)",
        "set_name": "Surging Sparks",
        "tcgplayer_id": "565630",
        "gtin": None,
        "spot_usd": 49.99,
        "source": "demo",
        "kind": "sealed",
    },
    {
        "card_id": "sealed:600518",
        "name": "Prismatic Evolutions Booster Bundle",
        "set_name": "Prismatic Evolutions",
        "tcgplayer_id": "600518",
        "gtin": None,
        "spot_usd": 64.5,
        "source": "demo",
        "kind": "sealed",
    },
    {
        "card_id": "sealed:593355",
        "name": "Prismatic Evolutions Elite Trainer Box (ETB)",
        "set_name": "Prismatic Evolutions",
        "tcgplayer_id": "593355",
        "gtin": None,
        "spot_usd": 89.99,
        "source": "demo",
        "kind": "sealed",
    },
    {
        "card_id": "sealed:544199",
        "name": "Scarlet & Violet—151 Ultra-Premium Collection (UPC)",
        "set_name": "151",
        "tcgplayer_id": "544199",
        "gtin": None,
        "spot_usd": 129.99,
        "source": "demo",
        "kind": "sealed",
    },
    {
        "card_id": "sealed:539927",
        "name": "Paldean Fates Elite Trainer Box (ETB)",
        "set_name": "Paldean Fates",
        "tcgplayer_id": "539927",
        "gtin": None,
        "spot_usd": 79.99,
        "source": "demo",
        "kind": "sealed",
    },
    {
        "card_id": "sealed:561447",
        "name": "Stellar Crown Elite Trainer Box (ETB)",
        "set_name": "Stellar Crown",
        "tcgplayer_id": "561447",
        "gtin": None,
        "spot_usd": 54.99,
        "source": "demo",
        "kind": "sealed",
    },
    {
        "card_id": "sealed:546116",
        "name": "Twilight Masquerade Elite Trainer Box (ETB)",
        "set_name": "Twilight Masquerade",
        "tcgplayer_id": "546116",
        "gtin": None,
        "spot_usd": 59.99,
        "source": "demo",
        "kind": "sealed",
    },
    {
        "card_id": "sealed:542194",
        "name": "Temporal Forces Elite Trainer Box (ETB)",
        "set_name": "Temporal Forces",
        "tcgplayer_id": "542194",
        "gtin": None,
        "spot_usd": 54.99,
        "source": "demo",
        "kind": "sealed",
    },
]


def _with_tcp_images(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from justtcg_sealed import tcgplayer_product_image

    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        if not item.get("image_url"):
            item["image_url"] = tcgplayer_product_image(str(item.get("tcgplayer_id") or ""))
        out.append(item)
    return out


def _filter_demo(q: str | None) -> list[dict[str, Any]]:
    text = (q or "").strip().lower()
    if not text:
        rows = list(_DEMO_SEALED)
    else:
        rows = [
            row
            for row in _DEMO_SEALED
            if text in str(row["name"]).lower()
            or text in str(row.get("set_name") or "").lower()
            or text in str(row.get("tcgplayer_id") or "").lower()
        ]
    return _with_tcp_images(rows)


def quote_sealed_products(
    *,
    q: str | None = None,
    tcgplayer_id: str | None = None,
    gtin: str | None = None,
    limit: int = 8,
    allow_showcase: bool = False,
) -> dict[str, Any]:
    from justtcg_client import justtcg_api_key

    limit = max(1, min(int(limit or 8), 20))
    has_key = bool(justtcg_api_key())
    has_query = bool(q or tcgplayer_id or gtin)
    if not has_query:
        if not allow_showcase:
            return {
                "items": [],
                "source": "empty",
                "justtcg_configured": has_key,
                "error": "Provide q, tcgplayer_id, or gtin.",
            }
        # Soft Ink /sealed desk: curated demo showcase until we persist a sealed board.
        hits = _filter_demo(None)
        return {
            "items": hits[:limit],
            "source": "demo",
            "justtcg_configured": has_key,
        }

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
    image = hit.get("image_url")
    if not image:
        from justtcg_sealed import tcgplayer_product_image

        image = tcgplayer_product_image(str(hit.get("tcgplayer_id") or ""))
    row = {
        "id": card_id,
        "name": name,
        "supertype": "Sealed",
        "rarity": "Sealed",
        "set_name": hit.get("set_name"),
        "market_price": market,
        "pokewallet_id": None,
        "tcgplayer_id": hit.get("tcgplayer_id"),
        "image_url": image,
    }
    if demo_mode():
        return {**hit, "image_url": image, "ensured": True, "demo": True}

    from database import upsert_cards

    upsert_cards([row])
    return {**hit, "image_url": image, "ensured": True, "demo": False}

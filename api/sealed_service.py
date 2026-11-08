"""Sealed product quotes + catalog ensure for portfolio MTM."""

from __future__ import annotations

import logging
import re
from typing import Any

from api.demo_mode import demo_mode

LOG = logging.getLogger("kestrel.api.sealed")

# Demo / no-key Soft Ink showcase — verified Pokémon TCGPlayer product ids
# (CDN art must match the named sealed SKU; wrong ids previously pointed at MTG/FAB cards).
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
        "card_id": "sealed:502005",
        "name": "Scarlet & Violet—151 Ultra-Premium Collection (UPC)",
        "set_name": "151",
        "tcgplayer_id": "502005",
        "gtin": None,
        "spot_usd": 129.99,
        "source": "demo",
        "kind": "sealed",
    },
    {
        "card_id": "sealed:528040",
        "name": "Paldean Fates Elite Trainer Box (ETB)",
        "set_name": "Paldean Fates",
        "tcgplayer_id": "528040",
        "gtin": None,
        "spot_usd": 79.99,
        "source": "demo",
        "kind": "sealed",
    },
    {
        "card_id": "sealed:557350",
        "name": "Stellar Crown Elite Trainer Box (ETB)",
        "set_name": "Stellar Crown",
        "tcgplayer_id": "557350",
        "gtin": None,
        "spot_usd": 54.99,
        "source": "demo",
        "kind": "sealed",
    },
    {
        "card_id": "sealed:543845",
        "name": "Twilight Masquerade Elite Trainer Box (ETB)",
        "set_name": "Twilight Masquerade",
        "tcgplayer_id": "543845",
        "gtin": None,
        "spot_usd": 59.99,
        "source": "demo",
        "kind": "sealed",
    },
    {
        "card_id": "sealed:532848",
        "name": "Temporal Forces Elite Trainer Box (Iron Leaves ex)",
        "set_name": "Temporal Forces",
        "tcgplayer_id": "532848",
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


def _token_overlap(expected: str, actual: str) -> bool:
    """True when live JustTCG title still smells like the curated seed name."""
    stop = {
        "the",
        "and",
        "of",
        "a",
        "an",
        "ex",
        "box",
        "set",
        "pokemon",
        "pokémon",
        "tcg",
    }
    exp = {
        t
        for t in re.findall(r"[a-z0-9]+", (expected or "").lower())
        if len(t) >= 3 and t not in stop
    }
    act = {
        t
        for t in re.findall(r"[a-z0-9]+", (actual or "").lower())
        if len(t) >= 3 and t not in stop
    }
    if not exp or not act:
        return False
    return len(exp & act) >= min(2, len(exp))


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


def _sniff_live_showcase(*, limit: int) -> list[dict[str, Any]]:
    """Quote curated TCP seeds live; drop rows that fail name sniff (M3.1)."""
    from justtcg_sealed import quote_sealed, tcgplayer_product_image

    out: list[dict[str, Any]] = []
    for seed in _DEMO_SEALED:
        if len(out) >= limit:
            break
        tid = str(seed.get("tcgplayer_id") or "").strip()
        if not tid:
            continue
        try:
            hits = quote_sealed(tcgplayer_id=tid, limit=1)
        except Exception as exc:
            LOG.info("sealed seed live quote failed (%s): %s", tid, exc)
            continue
        if not hits:
            LOG.info("sealed seed sniff empty for tcp=%s", tid)
            continue
        hit = dict(hits[0])
        live_name = str(hit.get("name") or "")
        if not _token_overlap(str(seed.get("name") or ""), live_name):
            LOG.info(
                "sealed seed sniff rejected tcp=%s expected=%r got=%r",
                tid,
                seed.get("name"),
                live_name,
            )
            continue
        # Prefer verified TCP CDN when JustTCG omits art.
        if not hit.get("image_url"):
            hit["image_url"] = tcgplayer_product_image(tid)
        hit["tcgplayer_id"] = tid
        hit["card_id"] = f"sealed:{tid}"
        hit["source"] = "justtcg"
        hit["kind"] = "sealed"
        out.append(hit)
    return out


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
        # Soft Ink /sealed desk: live-sniff curated TCP seeds when JustTCG is up;
        # otherwise show illustrative demo spots with verified CDN art only.
        if has_key and not demo_mode():
            live = _sniff_live_showcase(limit=limit)
            if live:
                return {
                    "items": live[:limit],
                    "source": "justtcg",
                    "justtcg_configured": True,
                }
            LOG.info("sealed showcase sniff empty — falling back to demo seed")
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

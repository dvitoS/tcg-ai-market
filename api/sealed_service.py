"""Sealed product quotes + catalog ensure for portfolio MTM."""

from __future__ import annotations

import logging
import re
from typing import Any

from api.demo_mode import demo_mode

LOG = logging.getLogger("kestrel.api.sealed")

# Demo / no-key Soft Ink showcase — verified Pokémon TCGPlayer product ids
# (CDN art must match the named sealed SKU; wrong ids previously pointed at MTG/FAB cards).
# Spots are illustrative until JustTCG is queried live (TCP marketPrice snapshot).
_DEMO_SEALED: list[dict[str, Any]] = [
    # Destined Rivals
    {
        "card_id": "sealed:624679",
        "name": "Destined Rivals Booster Box",
        "set_name": "Destined Rivals",
        "tcgplayer_id": "624679",
        "gtin": None,
        "spot_usd": 381.24,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "booster_box",
        "packs": 36,
    },
    {
        "card_id": "sealed:624676",
        "name": "Destined Rivals Elite Trainer Box (ETB)",
        "set_name": "Destined Rivals",
        "tcgplayer_id": "624676",
        "gtin": None,
        "spot_usd": 106.12,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:625670",
        "name": "Destined Rivals Booster Bundle",
        "set_name": "Destined Rivals",
        "tcgplayer_id": "625670",
        "gtin": None,
        "spot_usd": 63.95,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "bundle",
        "packs": 6,
    },
    {
        "card_id": "sealed:624681",
        "name": "Destined Rivals Half Booster Box",
        "set_name": "Destined Rivals",
        "tcgplayer_id": "624681",
        "gtin": None,
        "spot_usd": 317.5,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "half_box",
        "packs": 18,
    },
    # Journey Together
    {
        "card_id": "sealed:610931",
        "name": "Journey Together Booster Box",
        "set_name": "Journey Together",
        "tcgplayer_id": "610931",
        "gtin": None,
        "spot_usd": 204.08,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "booster_box",
        "packs": 36,
    },
    {
        "card_id": "sealed:610930",
        "name": "Journey Together Elite Trainer Box (ETB)",
        "set_name": "Journey Together",
        "tcgplayer_id": "610930",
        "gtin": None,
        "spot_usd": 132.93,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:610953",
        "name": "Journey Together Booster Bundle",
        "set_name": "Journey Together",
        "tcgplayer_id": "610953",
        "gtin": None,
        "spot_usd": 38.9,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "bundle",
        "packs": 6,
    },
    # Surging Sparks
    {
        "card_id": "sealed:565606",
        "name": "Surging Sparks Booster Box",
        "set_name": "Surging Sparks",
        "tcgplayer_id": "565606",
        "gtin": None,
        "spot_usd": 302.69,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "booster_box",
        "packs": 36,
    },
    {
        "card_id": "sealed:565630",
        "name": "Surging Sparks Elite Trainer Box (ETB)",
        "set_name": "Surging Sparks",
        "tcgplayer_id": "565630",
        "gtin": None,
        "spot_usd": 115.6,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:565629",
        "name": "Surging Sparks Booster Bundle",
        "set_name": "Surging Sparks",
        "tcgplayer_id": "565629",
        "gtin": None,
        "spot_usd": 69.85,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "bundle",
        "packs": 6,
    },
    # Prismatic Evolutions
    {
        "card_id": "sealed:600518",
        "name": "Prismatic Evolutions Booster Bundle",
        "set_name": "Prismatic Evolutions",
        "tcgplayer_id": "600518",
        "gtin": None,
        "spot_usd": 73.78,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "bundle",
        "packs": 6,
    },
    {
        "card_id": "sealed:593355",
        "name": "Prismatic Evolutions Elite Trainer Box (ETB)",
        "set_name": "Prismatic Evolutions",
        "tcgplayer_id": "593355",
        "gtin": None,
        "spot_usd": 114.37,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:622770",
        "name": "Prismatic Evolutions Super-Premium Collection",
        "set_name": "Prismatic Evolutions",
        "tcgplayer_id": "622770",
        "gtin": None,
        "spot_usd": 238.98,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "collection",
        "packs": None,
    },
    # Stellar Crown / Twilight / Temporal
    {
        "card_id": "sealed:557354",
        "name": "Stellar Crown Booster Box",
        "set_name": "Stellar Crown",
        "tcgplayer_id": "557354",
        "gtin": None,
        "spot_usd": 309.96,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "booster_box",
        "packs": 36,
    },
    {
        "card_id": "sealed:557350",
        "name": "Stellar Crown Elite Trainer Box (ETB)",
        "set_name": "Stellar Crown",
        "tcgplayer_id": "557350",
        "gtin": None,
        "spot_usd": 160.81,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:543846",
        "name": "Twilight Masquerade Booster Box",
        "set_name": "Twilight Masquerade",
        "tcgplayer_id": "543846",
        "gtin": None,
        "spot_usd": 334.85,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "booster_box",
        "packs": 36,
    },
    {
        "card_id": "sealed:543845",
        "name": "Twilight Masquerade Elite Trainer Box (ETB)",
        "set_name": "Twilight Masquerade",
        "tcgplayer_id": "543845",
        "gtin": None,
        "spot_usd": 103.87,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:536225",
        "name": "Temporal Forces Booster Box",
        "set_name": "Temporal Forces",
        "tcgplayer_id": "536225",
        "gtin": None,
        "spot_usd": 323.98,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "booster_box",
        "packs": 36,
    },
    {
        "card_id": "sealed:532848",
        "name": "Temporal Forces Elite Trainer Box (Iron Leaves ex)",
        "set_name": "Temporal Forces",
        "tcgplayer_id": "532848",
        "gtin": None,
        "spot_usd": 126.82,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:541017",
        "name": "Temporal Forces Booster Bundle",
        "set_name": "Temporal Forces",
        "tcgplayer_id": "541017",
        "gtin": None,
        "spot_usd": 87.21,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "bundle",
        "packs": 6,
    },
    # Paldean Fates / 151 / Shrouded
    {
        "card_id": "sealed:528040",
        "name": "Paldean Fates Elite Trainer Box (ETB)",
        "set_name": "Paldean Fates",
        "tcgplayer_id": "528040",
        "gtin": None,
        "spot_usd": 432.84,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:528771",
        "name": "Paldean Fates Booster Bundle",
        "set_name": "Paldean Fates",
        "tcgplayer_id": "528771",
        "gtin": None,
        "spot_usd": 167.68,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "bundle",
        "packs": 6,
    },
    {
        "card_id": "sealed:502005",
        "name": "Scarlet & Violet—151 Ultra-Premium Collection (UPC)",
        "set_name": "151",
        "tcgplayer_id": "502005",
        "gtin": None,
        "spot_usd": 847.77,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "collection",
        "packs": None,
    },
    {
        "card_id": "sealed:502000",
        "name": "Scarlet & Violet—151 Booster Bundle",
        "set_name": "151",
        "tcgplayer_id": "502000",
        "gtin": None,
        "spot_usd": 164.77,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "bundle",
        "packs": 6,
    },
    {
        "card_id": "sealed:503313",
        "name": "Scarlet & Violet—151 Elite Trainer Box (ETB)",
        "set_name": "151",
        "tcgplayer_id": "503313",
        "gtin": None,
        "spot_usd": 493.08,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:552999",
        "name": "Shrouded Fable Elite Trainer Box (ETB)",
        "set_name": "Shrouded Fable",
        "tcgplayer_id": "552999",
        "gtin": None,
        "spot_usd": 112.59,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:553031",
        "name": "Shrouded Fable Booster Bundle",
        "set_name": "Shrouded Fable",
        "tcgplayer_id": "553031",
        "gtin": None,
        "spot_usd": 56.66,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "bundle",
        "packs": 6,
    },
    # SV base + Paldea / Obsidian / Paradox
    {
        "card_id": "sealed:476452",
        "name": "Scarlet & Violet Booster Box",
        "set_name": "Scarlet & Violet",
        "tcgplayer_id": "476452",
        "gtin": None,
        "spot_usd": 298.51,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "booster_box",
        "packs": 36,
    },
    {
        "card_id": "sealed:493975",
        "name": "Paldea Evolved Booster Box",
        "set_name": "Paldea Evolved",
        "tcgplayer_id": "493975",
        "gtin": None,
        "spot_usd": 461.79,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "booster_box",
        "packs": 36,
    },
    {
        "card_id": "sealed:493974",
        "name": "Paldea Evolved Elite Trainer Box (ETB)",
        "set_name": "Paldea Evolved",
        "tcgplayer_id": "493974",
        "gtin": None,
        "spot_usd": 202.05,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:501257",
        "name": "Obsidian Flames Booster Box",
        "set_name": "Obsidian Flames",
        "tcgplayer_id": "501257",
        "gtin": None,
        "spot_usd": 381.73,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "booster_box",
        "packs": 36,
    },
    {
        "card_id": "sealed:501264",
        "name": "Obsidian Flames Elite Trainer Box (ETB)",
        "set_name": "Obsidian Flames",
        "tcgplayer_id": "501264",
        "gtin": None,
        "spot_usd": 269.79,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:512821",
        "name": "Paradox Rift Booster Box",
        "set_name": "Paradox Rift",
        "tcgplayer_id": "512821",
        "gtin": None,
        "spot_usd": 281.73,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "booster_box",
        "packs": 36,
    },
    {
        "card_id": "sealed:512813",
        "name": "Paradox Rift Elite Trainer Box (Iron Valiant)",
        "set_name": "Paradox Rift",
        "tcgplayer_id": "512813",
        "gtin": None,
        "spot_usd": 135.69,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    # Black Bolt / White Flare / Mega / Phantasmal / Ascended / Crown Zenith
    {
        "card_id": "sealed:630686",
        "name": "Black Bolt Elite Trainer Box (ETB)",
        "set_name": "Black Bolt",
        "tcgplayer_id": "630686",
        "gtin": None,
        "spot_usd": 153.25,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:630431",
        "name": "Black Bolt Booster Bundle",
        "set_name": "Black Bolt",
        "tcgplayer_id": "630431",
        "gtin": None,
        "spot_usd": 96.71,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "bundle",
        "packs": 6,
    },
    {
        "card_id": "sealed:630689",
        "name": "White Flare Elite Trainer Box (ETB)",
        "set_name": "White Flare",
        "tcgplayer_id": "630689",
        "gtin": None,
        "spot_usd": 143.05,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:630696",
        "name": "White Flare Booster Bundle",
        "set_name": "White Flare",
        "tcgplayer_id": "630696",
        "gtin": None,
        "spot_usd": 92.15,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "bundle",
        "packs": 6,
    },
    {
        "card_id": "sealed:644279",
        "name": "Mega Evolution Elite Trainer Box (Mega Gardevoir)",
        "set_name": "Mega Evolution",
        "tcgplayer_id": "644279",
        "gtin": None,
        "spot_usd": 107.9,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:644300",
        "name": "Mega Evolution Enhanced Booster Box",
        "set_name": "Mega Evolution",
        "tcgplayer_id": "644300",
        "gtin": None,
        "spot_usd": 289.56,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "booster_box",
        "packs": 36,
    },
    {
        "card_id": "sealed:654137",
        "name": "Phantasmal Flames Booster Box",
        "set_name": "Phantasmal Flames",
        "tcgplayer_id": "654137",
        "gtin": None,
        "spot_usd": 383.35,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "booster_box",
        "packs": 36,
    },
    {
        "card_id": "sealed:654136",
        "name": "Phantasmal Flames Elite Trainer Box (ETB)",
        "set_name": "Phantasmal Flames",
        "tcgplayer_id": "654136",
        "gtin": None,
        "spot_usd": 137.81,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:668496",
        "name": "Ascended Heroes Elite Trainer Box (ETB)",
        "set_name": "Ascended Heroes",
        "tcgplayer_id": "668496",
        "gtin": None,
        "spot_usd": 126.94,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 9,
    },
    {
        "card_id": "sealed:453470",
        "name": "Crown Zenith Elite Trainer Box (ETB)",
        "set_name": "Crown Zenith",
        "tcgplayer_id": "453470",
        "gtin": None,
        "spot_usd": 314.66,
        "source": "demo",
        "kind": "sealed",
        "product_kind": "etb",
        "packs": 10,
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


def normalize_sealed_set_name(raw: str | None) -> str:
    """Map JustTCG set labels onto Soft Ink catalog ``set_name`` values.

    Live quotes often arrive as ``SV10: Destined Rivals`` or
    ``SV01: Scarlet & Violet Base Set`` — exact board filters miss those.
    """
    text = str(raw or "").strip()
    if not text:
        return ""
    # Drop leading expansion codes: SV10:, SV03.5:, ME01:, etc.
    text = re.sub(
        r"^[A-Za-z]{1,6}\d{0,2}(?:\.\d+)?(?:pt\d+)?\s*:\s*",
        "",
        text,
    ).strip()
    aliases = {
        "scarlet & violet base set": "Scarlet & Violet",
        "scarlet and violet base set": "Scarlet & Violet",
        "scarlet and violet": "Scarlet & Violet",
        "pokemon scarlet & violet": "Scarlet & Violet",
        "151": "151",
        "scarlet & violet—151": "151",
        "scarlet & violet - 151": "151",
        "scarlet & violet 151": "151",
    }
    return aliases.get(text.lower(), text)


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


def find_demo_sealed(tcgplayer_id: str) -> dict[str, Any] | None:
    tid = re.sub(r"[^0-9]", "", str(tcgplayer_id or "").strip())
    if not tid:
        return None
    for row in _DEMO_SEALED:
        if str(row.get("tcgplayer_id") or "") == tid:
            return _with_tcp_images([row])[0]
    return None


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
        # Prefer curated catalog set_name — JustTCG often prefixes SV10:/SV01:.
        hit["set_name"] = seed.get("set_name") or normalize_sealed_set_name(
            hit.get("set_name")
        )
        hit["product_kind"] = seed.get("product_kind")
        hit["packs"] = seed.get("packs")
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

    limit = max(1, min(int(limit or 8), 48))
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


_CHASE_RARITY_NEEDLES = (
    "special illustration",
    "illustration rare",
    "hyper rare",
    "secret rare",
    "ultra rare",
    "double rare",
    "amazing rare",
    "radiant",
    "ace spec",
    "gold star",
    "shiny rare",
    "shiny ultra",
)


def _is_chase_rarity(rarity: str | None) -> bool:
    text = str(rarity or "").strip().lower()
    if not text:
        return False
    return any(n in text for n in _CHASE_RARITY_NEEDLES)


def _group_key(rarity: str | None) -> str | None:
    text = str(rarity or "").strip().lower()
    if "special illustration" in text:
        return "sir"
    if "illustration rare" in text:
        return "ir"
    if "hyper rare" in text or "secret" in text:
        return "hyper"
    return None


def _set_hits(set_name: str, *, limit: int = 48) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (chase cards, rarity groups) for a sealed product's set."""
    from api.catalog_service import filter_board, load_board, row_to_card

    board, source = load_board()
    wanted = normalize_sealed_set_name(set_name) or str(set_name or "").strip()
    if board is None or board.empty or not wanted:
        return [], []
    scoped = filter_board(board, set_name=wanted, mode="browse")
    # Fallback: board may still use a near-label (rare); try case-insensitive contains.
    if (scoped is None or scoped.empty) and "set_name" in board.columns:
        needle = wanted.lower()
        mask = board["set_name"].astype(str).str.lower() == needle
        if not mask.any():
            mask = board["set_name"].astype(str).str.lower().str.contains(
                re.escape(needle), na=False
            )
        scoped = board[mask].reset_index(drop=True) if mask.any() else scoped
    if scoped is None or scoped.empty:
        return [], []

    # Prefer chase rarities; fall back to top-priced Pokémon in the set.
    chase = scoped[scoped["rarity"].map(_is_chase_rarity)] if "rarity" in scoped.columns else scoped.iloc[0:0]
    pool = chase if not chase.empty else scoped
    if "supertype" in pool.columns:
        poke = pool[pool["supertype"].astype(str).str.lower().str.contains("pok", na=False)]
        if not poke.empty:
            pool = poke
    price_col = "price" if "price" in pool.columns else "market_price"
    if price_col in pool.columns:
        pool = pool.sort_values(price_col, ascending=False, na_position="last")
    cards = [row_to_card(row) for _, row in pool.head(max(1, min(limit, 72))).iterrows()]

    groups: list[dict[str, Any]] = []
    if "rarity" in scoped.columns and price_col in scoped.columns:
        for key, label in (
            ("ir", "Illustration Rares"),
            ("sir", "Special Illustration Rares"),
            ("hyper", "Hyper / Secret Rares"),
        ):
            subset = scoped[scoped["rarity"].map(lambda r: _group_key(r) == key)]
            if subset.empty:
                continue
            prices = subset[price_col].dropna()
            total = float(prices.sum()) if not prices.empty else 0.0
            # Featured = top 3 by price for SIR strip.
            top = [
                row_to_card(row)
                for _, row in subset.sort_values(price_col, ascending=False, na_position="last")
                .head(3)
                .iterrows()
            ]
            groups.append(
                {
                    "key": key,
                    "label": label,
                    "count": int(len(subset)),
                    "total_usd": round(total, 2),
                    "featured": top,
                }
            )
    LOG.info("sealed set hits set=%r source=%s cards=%s groups=%s", set_name, source, len(cards), len(groups))
    return cards, groups


def sealed_product_detail(tcgplayer_id: str, *, hits_limit: int = 48) -> dict[str, Any] | None:
    """Resolve one sealed SKU + set singles (box vs hits desk)."""
    tid = re.sub(r"[^0-9]", "", str(tcgplayer_id or "").strip())
    if not tid:
        return None

    product = find_demo_sealed(tid)
    source = "demo" if product else "empty"
    from justtcg_client import justtcg_api_key

    has_key = bool(justtcg_api_key())
    if has_key and not demo_mode():
        try:
            from justtcg_sealed import quote_sealed, tcgplayer_product_image

            live = quote_sealed(tcgplayer_id=tid, limit=1)
            if live:
                hit = dict(live[0])
                if product and not _token_overlap(
                    str(product.get("name") or ""), str(hit.get("name") or "")
                ):
                    LOG.info("sealed detail sniff rejected tcp=%s", tid)
                else:
                    seed = product
                    if not hit.get("image_url"):
                        hit["image_url"] = tcgplayer_product_image(tid)
                    hit["tcgplayer_id"] = tid
                    hit["card_id"] = f"sealed:{tid}"
                    hit["kind"] = "sealed"
                    hit["source"] = "justtcg"
                    # Catalog set_name wins — JustTCG prefixes break board filters.
                    hit["set_name"] = (seed or {}).get("set_name") or normalize_sealed_set_name(
                        hit.get("set_name")
                    )
                    if seed:
                        hit["product_kind"] = seed.get("product_kind")
                        hit["packs"] = seed.get("packs")
                        hit["name"] = hit.get("name") or seed.get("name")
                    product = hit
                    source = "justtcg"
        except Exception as exc:
            LOG.info("sealed detail live quote failed (%s): %s", tid, exc)

    if not product:
        return None

    set_name = normalize_sealed_set_name(product.get("set_name")) or str(
        product.get("set_name") or ""
    ).strip()
    product["set_name"] = set_name or product.get("set_name")
    shelf = [
        row
        for row in _with_tcp_images(
            [
                dict(r)
                for r in _DEMO_SEALED
                if normalize_sealed_set_name(r.get("set_name")) == set_name
            ]
        )
        if str(row.get("tcgplayer_id") or "") != tid
    ][:6]

    hits, groups = _set_hits(set_name, limit=hits_limit) if set_name else ([], [])
    spot = product.get("spot_usd")
    try:
        spot_f = float(spot) if spot is not None else None
    except (TypeError, ValueError):
        spot_f = None

    summary = None
    ir = next((g for g in groups if g.get("key") == "ir"), None)
    sir = next((g for g in groups if g.get("key") == "sir"), None)
    if spot_f and spot_f > 0 and ir and ir.get("total_usd") is not None:
        delta = round(spot_f - float(ir["total_usd"]), 2)
        summary = {
            "ir_vs_product_usd": delta,
            "sir_boxes": round(float(sir["total_usd"]) / spot_f, 2) if sir and sir.get("total_usd") else None,
        }

    return {
        "product": product,
        "shelf": shelf,
        "hits": hits,
        "groups": groups,
        "summary": summary,
        "source": source,
        "justtcg_configured": has_key,
        "set_name": set_name or None,
    }

"""TCGPlayer finish / printing labels for Soft Ink card descriptions.

Pokémon TCG API exposes finishes under ``tcgplayer.prices`` keys
(``normal``, ``holofoil``, ``reverseHolofoil``, ``1stEditionNormal``, …).
Soft Ink board spot is a single NM lane; these labels list every printing
the product has — including unknown keys humanized from camelCase.
"""

from __future__ import annotations

import re
from typing import Any

# Canonical Soft Ink labels (order = display order).
# Keys are alnum-lower forms of TCGPlayer / Pokémon TCG API price keys.
FINISH_KEY_MAP: dict[str, str] = {
    "normal": "Normal",
    "nonfoil": "Normal",
    "nonholo": "Normal",
    "holofoil": "Holofoil",
    "holo": "Holofoil",
    "foil": "Foil",
    "reverseholofoil": "Reverse Holofoil",
    "reverseholo": "Reverse Holofoil",
    "reverse": "Reverse Holofoil",
    "1stedition": "1st Edition",
    "1steditionnormal": "1st Edition Normal",
    "1steditionholofoil": "1st Edition Holofoil",
    "1steditionholo": "1st Edition Holofoil",
    "1steditionreverseholofoil": "1st Edition Reverse Holofoil",
    "unlimited": "Unlimited",
    "unlimitednormal": "Unlimited Normal",
    "unlimitedholofoil": "Unlimited Holofoil",
    "unlimitedholo": "Unlimited Holofoil",
    "unlimitedreverseholofoil": "Unlimited Reverse Holofoil",
    "shadowless": "Shadowless",
    "shadowlessholofoil": "Shadowless Holofoil",
    "cosmosholofoil": "Cosmos Holofoil",
    "cosmosholo": "Cosmos Holofoil",
    "cosmos": "Cosmos Holofoil",
    "amazingrare": "Amazing Rare",
    "rainbowrare": "Rainbow Rare",
    "gold": "Gold",
    "etched": "Etched",
    "etchedholofoil": "Etched Holofoil",
}

DISPLAY_ORDER = (
    "Normal",
    "Holofoil",
    "Reverse Holofoil",
    "Foil",
    "1st Edition",
    "1st Edition Normal",
    "1st Edition Holofoil",
    "1st Edition Reverse Holofoil",
    "Unlimited",
    "Unlimited Normal",
    "Unlimited Holofoil",
    "Unlimited Reverse Holofoil",
    "Shadowless",
    "Shadowless Holofoil",
    "Cosmos Holofoil",
    "Amazing Rare",
    "Rainbow Rare",
    "Gold",
    "Etched",
    "Etched Holofoil",
)

_LOT_ALIASES = {
    "reverse": "Reverse Holofoil",
    "reverse holo": "Reverse Holofoil",
    "reverse holofoil": "Reverse Holofoil",
    "holo": "Holofoil",
    "holofoil": "Holofoil",
    "foil": "Foil",
    "normal": "Normal",
    "nonfoil": "Normal",
    "non-foil": "Normal",
}


def _canon_key(raw: str) -> str:
    return "".join(ch for ch in str(raw or "").lower() if ch.isalnum())


def humanize_finish_key(key: str) -> str:
    """Turn camelCase / snake keys into a readable label."""
    text = str(key or "").strip()
    if not text:
        return ""
    # 1stEditionHolofoil → 1st Edition Holofoil
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Za-z])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([A-Za-z])", r"\1 \2", text)
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    parts = []
    for word in text.split(" "):
        low = word.lower()
        if low in {"1st", "2nd", "3rd"}:
            parts.append(low)
        elif low == "holofoil":
            parts.append("Holofoil")
        elif low == "holo":
            parts.append("Holo")
        else:
            parts.append(word[:1].upper() + word[1:] if word else word)
    return " ".join(parts)


def label_for_tcgplayer_key(key: str) -> str | None:
    raw = str(key or "").strip()
    if not raw:
        return None
    mapped = FINISH_KEY_MAP.get(_canon_key(raw))
    if mapped:
        return mapped
    # Already a display label.
    if raw in DISPLAY_ORDER or raw in FINISH_KEY_MAP.values():
        return raw
    alias = _LOT_ALIASES.get(raw.lower())
    if alias:
        return alias
    # Never drop unknown TCGPlayer keys — show them humanized.
    return humanize_finish_key(raw) or None


def extract_finishes_from_tcgplayer(card: dict[str, Any] | None) -> list[str]:
    """Return ordered finish labels present under ``tcgplayer.prices``."""
    if not isinstance(card, dict):
        return []
    tcg = card.get("tcgplayer") or {}
    prices = tcg.get("prices") if isinstance(tcg, dict) else None
    if not isinstance(prices, dict) or not prices:
        return []
    found: set[str] = set()
    for key in prices.keys():
        label = label_for_tcgplayer_key(str(key))
        if label:
            found.add(label)
    return _ordered(found)


def finishes_from_rarity(rarity: str | None) -> list[str]:
    """Soft hint from rarity text only (not a full finish inventory)."""
    text = str(rarity or "").strip().lower()
    if not text:
        return []
    if "reverse" in text:
        return ["Reverse Holofoil"]
    if "rainbow" in text:
        return ["Rainbow Rare"]
    if "amazing" in text:
        return ["Amazing Rare"]
    if "gold" in text:
        return ["Gold"]
    if (
        "holo" in text
        or "foil" in text
        or "ultra rare" in text
        or "double rare" in text
        or "illustration" in text
        or "hyper" in text
        or "secret" in text
        or "shiny" in text
        or "radiant" in text
        or "ace spec" in text
    ):
        return ["Holofoil"]
    return []


def _ordered(found: set[str]) -> list[str]:
    known = [label for label in DISPLAY_ORDER if label in found]
    extra = sorted(found - set(DISPLAY_ORDER))
    return known + extra


def parse_finishes_blob(raw: Any) -> list[str]:
    """Parse DB text / list into ordered unique finish labels."""
    if raw is None:
        return []
    if isinstance(raw, list):
        parts = [str(x).strip() for x in raw if str(x).strip()]
    else:
        text = str(raw).strip()
        if not text:
            return []
        parts = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
    found: set[str] = set()
    for part in parts:
        label = label_for_tcgplayer_key(part)
        if label:
            found.add(label)
    return _ordered(found)


def finishes_blob(finishes: list[str]) -> str | None:
    cleaned = parse_finishes_blob(finishes)
    return ", ".join(cleaned) if cleaned else None


def resolve_finishes(
    *,
    stored: Any = None,
    rarity: str | None = None,
    pokemon_card: dict[str, Any] | None = None,
) -> list[str]:
    """Prefer stored → live TCGPlayer keys → rarity hint."""
    from_store = parse_finishes_blob(stored)
    if from_store:
        return from_store
    from_live = extract_finishes_from_tcgplayer(pokemon_card)
    if from_live:
        return from_live
    return finishes_from_rarity(rarity)

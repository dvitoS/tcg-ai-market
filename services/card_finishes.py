"""TCGPlayer finish / printing labels for Soft Ink card descriptions.

Pokémon TCG API exposes finishes under ``tcgplayer.prices`` keys
(``normal``, ``holofoil``, ``reverseHolofoil``, …). Soft Ink board spot is a
single NM lane; these labels tell the user which printings exist for the card.
"""

from __future__ import annotations

from typing import Any

# Canonical Soft Ink labels (order = display order).
FINISH_KEY_MAP: dict[str, str] = {
    "normal": "Normal",
    "holofoil": "Holofoil",
    "reverseholofoil": "Reverse Holofoil",
    "1steditionholofoil": "1st Edition Holofoil",
    "1steditionnormal": "1st Edition Normal",
    "unlimitedholofoil": "Unlimited Holofoil",
}

DISPLAY_ORDER = (
    "Normal",
    "Holofoil",
    "Reverse Holofoil",
    "1st Edition Normal",
    "1st Edition Holofoil",
    "Unlimited Holofoil",
)


def _canon_key(raw: str) -> str:
    return "".join(ch for ch in str(raw or "").lower() if ch.isalnum())


def label_for_tcgplayer_key(key: str) -> str | None:
    return FINISH_KEY_MAP.get(_canon_key(key))


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
    return [label for label in DISPLAY_ORDER if label in found]


def finishes_from_rarity(rarity: str | None) -> list[str]:
    """Soft hint from rarity text only (not a full finish inventory)."""
    text = str(rarity or "").strip().lower()
    if not text:
        return []
    if "reverse" in text:
        return ["Reverse Holofoil"]
    if "holo" in text:
        return ["Holofoil"]
    return []


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
        label = label_for_tcgplayer_key(part) or (
            part
            if part in DISPLAY_ORDER or part in FINISH_KEY_MAP.values()
            else None
        )
        # Accept already-canonical Soft Ink lot labels.
        if label is None:
            low = part.lower()
            if low == "reverse":
                label = "Reverse Holofoil"
            elif low == "holo":
                label = "Holofoil"
            elif low == "normal":
                label = "Normal"
        if label:
            found.add(label)
    return [label for label in DISPLAY_ORDER if label in found] + sorted(
        found - set(DISPLAY_ORDER)
    )


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

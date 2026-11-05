"""Condition / printing multipliers on NM board spots."""

from __future__ import annotations

from typing import Any

CONDITION_MULT: dict[str, float] = {
    "NM": 1.0,
    "LP": 0.85,
    "MP": 0.7,
    "HP": 0.5,
    "DMG": 0.3,
}

PRINTING_MULT: dict[str, float] = {
    "Normal": 1.0,
    "Reverse": 1.05,
    "Holo": 1.1,
}

RAW_CONDITIONS = tuple(CONDITION_MULT.keys())
PRINTINGS = tuple(PRINTING_MULT.keys())


def normalize_condition(value: Any) -> str:
    text = str(value or "NM").strip().upper()
    if text in CONDITION_MULT:
        return text
    # Graded / legacy labels — leave market at NM board (grade field carries PSA).
    return "NM"


def normalize_printing(value: Any) -> str:
    text = str(value or "Normal").strip()
    if not text:
        return "Normal"
    key = text[:1].upper() + text[1:].lower() if text.lower() != "holo" else "Holo"
    # Accept common aliases.
    aliases = {
        "normal": "Normal",
        "nonfoil": "Normal",
        "non-foil": "Normal",
        "reverse": "Reverse",
        "reverse holo": "Reverse",
        "reverseholo": "Reverse",
        "holo": "Holo",
        "holofoil": "Holo",
        "foil": "Holo",
    }
    mapped = aliases.get(text.lower().strip())
    if mapped:
        return mapped
    if key in PRINTING_MULT:
        return key
    return "Normal"


def condition_mult(value: Any) -> float:
    return float(CONDITION_MULT[normalize_condition(value)])


def printing_mult(value: Any) -> float:
    return float(PRINTING_MULT[normalize_printing(value)])


def lot_price_factor(*, condition: Any = "NM", printing: Any = "Normal") -> float:
    return condition_mult(condition) * printing_mult(printing)


def adjust_nm_price(
    nm_spot: float | None,
    *,
    condition: Any = "NM",
    printing: Any = "Normal",
) -> float | None:
    if nm_spot is None:
        return None
    try:
        base = float(nm_spot)
    except (TypeError, ValueError):
        return None
    if base != base:  # NaN
        return None
    return base * lot_price_factor(condition=condition, printing=printing)

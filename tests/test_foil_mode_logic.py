"""Mirror Soft Ink foilModeFromFinishes rules for CI without a TS runner."""

from __future__ import annotations


def foil_mode(finishes: list[str]) -> str | None:
    labels = [str(f or "").strip().lower() for f in finishes if str(f or "").strip()]
    if not labels:
        return None
    holo_needles = (
        "holofoil",
        "cosmos",
        "rainbow",
        "amazing",
        "etched",
        "gold",
        "foil",
    )
    has_reverse = any("reverse" in f for f in labels)
    has_holo = any(
        (not ("reverse" in f)) and any(n in f for n in holo_needles) for f in labels
    )
    if has_holo:
        return "holo"
    if has_reverse:
        return "reverse"
    return None


def test_foil_prefers_holo_when_both() -> None:
    assert foil_mode(["Normal", "Holofoil", "Reverse Holofoil"]) == "holo"


def test_foil_reverse_only() -> None:
    assert foil_mode(["Normal", "Reverse Holofoil"]) == "reverse"


def test_foil_cosmos() -> None:
    assert foil_mode(["Cosmos Holofoil"]) == "holo"


def test_foil_none() -> None:
    assert foil_mode(["Normal"]) is None
    assert foil_mode([]) is None

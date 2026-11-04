"""clean_cards respects no-floor vs USD floor."""

from __future__ import annotations

from pokemon_tcg_client import clean_cards


def _card(card_id: str, price: float | None) -> dict:
    tcg = {}
    if price is not None:
        tcg = {"prices": {"holofoil": {"market": price}}}
    return {
        "id": card_id,
        "name": card_id,
        "supertype": "Pokémon",
        "rarity": "Rare",
        "set": {"id": "sv1", "name": "Scarlet & Violet"},
        "images": {"small": "https://example.com/x.png"},
        "tcgplayer": tcg,
    }


def test_clean_cards_keeps_unpriced_when_no_floor() -> None:
    raw = [_card("a-1", 1.0), _card("a-2", None), _card("a-3", 0.25)]
    out = clean_cards(raw, min_price=None)
    assert {row["id"] for row in out} == {"a-1", "a-2", "a-3"}


def test_clean_cards_zero_floor_keeps_unpriced() -> None:
    raw = [_card("a-1", None), _card("a-2", 0.5)]
    out = clean_cards(raw, min_price=0)
    assert {row["id"] for row in out} == {"a-1", "a-2"}


def test_clean_cards_five_dollar_floor() -> None:
    raw = [_card("a-1", 4.99), _card("a-2", 5.0), _card("a-3", None)]
    out = clean_cards(raw, min_price=5.0)
    assert [row["id"] for row in out] == ["a-2"]

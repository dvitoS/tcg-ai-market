"""TCGPlayer finish labels for Soft Ink card descriptions."""

from __future__ import annotations

from services.card_finishes import (
    extract_finishes_from_tcgplayer,
    finishes_from_rarity,
    parse_finishes_blob,
    resolve_finishes,
)
from pokemon_tcg_client import clean_cards


def test_extract_finishes_from_tcgplayer_prices() -> None:
    card = {
        "tcgplayer": {
            "prices": {
                "normal": {"market": 1.0},
                "reverseHolofoil": {"market": 2.0},
                "holofoil": {"market": 5.0},
                "1stEditionHolofoil": {"market": 40.0},
                "1stEditionNormal": {"market": 12.0},
                "unlimitedHolofoil": {"market": 8.0},
                "cosmosHolofoil": {"market": 3.0},
            }
        }
    }
    assert extract_finishes_from_tcgplayer(card) == [
        "Normal",
        "Holofoil",
        "Reverse Holofoil",
        "1st Edition Normal",
        "1st Edition Holofoil",
        "Unlimited Holofoil",
        "Cosmos Holofoil",
    ]


def test_unknown_tcgplayer_key_is_humanized_not_dropped() -> None:
    card = {
        "tcgplayer": {
            "prices": {
                "mysteryPromoFoil": {"market": 9.0},
            }
        }
    }
    assert extract_finishes_from_tcgplayer(card) == ["Mystery Promo Foil"]


def test_finishes_from_rarity_hint() -> None:
    assert finishes_from_rarity("Rare Holo") == ["Holofoil"]
    assert finishes_from_rarity("Rare Reverse Holo") == ["Reverse Holofoil"]
    assert finishes_from_rarity("Double Rare") == ["Holofoil"]
    assert finishes_from_rarity("Ultra Rare") == ["Holofoil"]
    assert finishes_from_rarity("Common") == []
    assert finishes_from_rarity("Promo") == []


def test_row_to_card_includes_finishes_hint() -> None:
    from api.catalog_service import row_to_card

    holo = row_to_card(
        {"id": "sv1-1", "name": "Sprigatito", "rarity": "Rare Holo", "price": 4.0}
    )
    assert holo["finishes"] == ["Holofoil"]
    ultra = row_to_card(
        {"id": "sv3-210", "name": "Eiscue ex", "rarity": "Ultra Rare", "price": 20.0}
    )
    assert ultra["finishes"] == ["Holofoil"]
    reverse = row_to_card(
        {
            "id": "sv1-2",
            "name": "Floragato",
            "rarity": "Uncommon",
            "finishes": "Reverse Holofoil",
            "price": 1.5,
        }
    )
    assert reverse["finishes"] == ["Reverse Holofoil"]
    plain = row_to_card({"id": "sv1-3", "name": "Basic", "rarity": "Common", "price": 0.2})
    assert plain["finishes"] == []


def test_resolve_prefers_stored_then_live_then_rarity() -> None:
    assert resolve_finishes(stored="Holofoil, Normal") == ["Normal", "Holofoil"]
    live = {
        "tcgplayer": {"prices": {"reverseHolofoil": {"market": 1.2}}},
    }
    assert resolve_finishes(pokemon_card=live) == ["Reverse Holofoil"]
    assert resolve_finishes(rarity="Rare Holo") == ["Holofoil"]


def test_parse_finishes_blob_accepts_lot_aliases() -> None:
    assert parse_finishes_blob("Reverse, Holo") == ["Holofoil", "Reverse Holofoil"]


def test_clean_cards_includes_finishes() -> None:
    raw = [
        {
            "id": "sv1-1",
            "name": "Sprigatito",
            "supertype": "Pokémon",
            "rarity": "Common",
            "set": {"id": "sv1", "name": "Scarlet & Violet"},
            "images": {"small": "https://example.com/x.png"},
            "tcgplayer": {
                "prices": {
                    "normal": {"market": 0.2},
                    "reverseHolofoil": {"market": 0.5},
                }
            },
        }
    ]
    out = clean_cards(raw, min_price=None)
    assert out[0]["finishes"] == "Normal, Reverse Holofoil"


def test_card_detail_enrich_finishes(monkeypatch) -> None:
    import pandas as pd
    from fastapi.testclient import TestClient

    from api.catalog_service import clear_board_cache
    from api.main import app

    clear_board_cache()
    board = pd.DataFrame(
        [
            {
                "id": "sv1-1",
                "name": "Sprigatito",
                "set_name": "Scarlet & Violet",
                "rarity": "Common",
                "price": 0.25,
                "market_price": 0.25,
                "predicted_price": 0.3,
                "expected_change_pct": 5.0,
                "signal": "HOLD",
                "confidence_ok": True,
                "conformal_ok": True,
                "history_points": 30,
                "image_url": "https://example.com/x.png",
            }
        ]
    )
    monkeypatch.setattr(
        "api.routers.cards.load_board",
        lambda: (board, "demo"),
    )
    monkeypatch.setattr(
        "api.routers.cards.load_card_history",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        "api.routers.cards.history_stats",
        lambda *_a, **_k: {
            "points": 0,
            "min_price": None,
            "max_price": None,
            "last_price": 0.25,
            "previous_price": None,
            "day_change_pct": None,
            "first_date": None,
            "last_date": None,
        },
    )
    monkeypatch.setattr(
        "api.routers.cards.build_card_explain",
        lambda **_k: {
            "confidence_level": "med",
            "confidence_ok": True,
            "confidence_reason": "ok",
            "hold_band_pct": 3.0,
            "horizon_days": 7,
            "rows": [],
        },
    )
    monkeypatch.setattr(
        "database.get_card",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "pokemon_tcg_client.fetch_pokemon_card",
        lambda *_a, **_k: {
            "tcgplayer": {
                "prices": {
                    "normal": {"market": 0.2},
                    "holofoil": {"market": 1.0},
                    "reverseHolofoil": {"market": 0.4},
                }
            }
        },
    )
    monkeypatch.setattr(
        "database.update_card_finishes",
        lambda *_a, **_k: False,
    )

    client = TestClient(app)
    res = client.get("/api/cards/sv1-1")
    assert res.status_code == 200
    body = res.json()
    assert body["card"]["finishes"] == [
        "Normal",
        "Holofoil",
        "Reverse Holofoil",
    ]
    assert body["card"]["finishes_source"] == "tcgplayer"

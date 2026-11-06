"""Phase C4 — JustTCG variant spots vs NM multipliers."""

from __future__ import annotations

from justtcg_client import pick_variant
from services.variant_spot import (
    clear_variant_spot_cache,
    needs_variant_lookup,
    resolve_variant_spots,
    spot_key,
)


def test_pick_variant_matches_condition_and_printing() -> None:
    variants = [
        {
            "id": "v-nm-normal",
            "condition": "Near Mint",
            "printing": "Normal",
            "price": 10.0,
        },
        {
            "id": "v-lp-reverse",
            "condition": "Lightly Played",
            "printing": "Reverse Holofoil",
            "price": 7.5,
        },
        {
            "id": "v-lp-holo",
            "condition": "Lightly Played",
            "printing": "Holofoil",
            "price": 8.2,
        },
    ]
    hit = pick_variant(variants, condition="LP", printing="Reverse")
    assert hit is not None
    assert hit["id"] == "v-lp-reverse"
    assert float(hit["price"]) == 7.5

    holo = pick_variant(variants, condition="LP", printing="Holo")
    assert holo is not None
    assert holo["id"] == "v-lp-holo"


def test_needs_variant_lookup() -> None:
    assert needs_variant_lookup("NM", "Normal") is False
    assert needs_variant_lookup("LP", "Normal") is True
    assert needs_variant_lookup("NM", "Holo") is True


def test_resolve_falls_back_to_multiplier_without_tcp(monkeypatch) -> None:
    clear_variant_spot_cache()
    monkeypatch.setattr(
        "services.variant_spot._tcp_for_card",
        lambda _cid: None,
    )
    out = resolve_variant_spots(
        [
            {
                "card_id": "sv3-1",
                "condition": "LP",
                "printing": "Normal",
                "nm_spot": 20.0,
            }
        ]
    )
    key = spot_key("sv3-1", "LP", "Normal")
    assert key in out
    assert out[key]["source"] == "multiplier"
    assert abs(float(out[key]["price"]) - 17.0) < 1e-9


def test_resolve_uses_justtcg_variant_price(monkeypatch) -> None:
    clear_variant_spot_cache()
    monkeypatch.setattr(
        "services.variant_spot._tcp_for_card",
        lambda _cid: "219042",
    )
    monkeypatch.setattr(
        "justtcg_client.justtcg_api_key",
        lambda: "test-key",
    )
    monkeypatch.setattr(
        "justtcg_client.batch_variant_lookups",
        lambda items: [
            {
                "tcgplayerId": "219042",
                "variants": [
                    {
                        "id": "var-lp",
                        "condition": "Lightly Played",
                        "printing": "Normal",
                        "price": 12.5,
                    }
                ],
            }
        ],
    )
    out = resolve_variant_spots(
        [
            {
                "card_id": "sv3-1",
                "condition": "LP",
                "printing": "Normal",
                "nm_spot": 20.0,
            }
        ]
    )
    key = spot_key("sv3-1", "LP", "Normal")
    assert out[key]["source"] == "justtcg_variant"
    assert abs(float(out[key]["price"]) - 12.5) < 1e-9
    assert out[key]["variant_id"] == "var-lp"
    # Effective factor vs NM board (12.5 / 20).
    assert abs(float(out[key]["price_factor"]) - 0.625) < 1e-9


def test_enrich_lots_prefers_variant_spot(monkeypatch) -> None:
    from api.portfolio_service import enrich_lots

    clear_variant_spot_cache()
    monkeypatch.setattr(
        "api.portfolio_service._board_indexes",
        lambda: (
            {
                "sv3-1": {
                    "id": "sv3-1",
                    "name": "Charmander",
                    "price": 20.0,
                    "predicted_price": 22.0,
                    "expected_change_pct": 10.0,
                    "signal": "BUY",
                    "rarity": "Common",
                    "set_name": "Obsidian Flames",
                    "image_url": None,
                }
            },
            {},
        ),
    )
    monkeypatch.setattr(
        "services.variant_spot.resolve_variant_spots",
        lambda _reqs: {
            spot_key("sv3-1", "LP", "Normal"): {
                "price": 11.0,
                "source": "justtcg_variant",
                "variant_id": "v1",
                "price_factor": 0.55,
                "tcgplayer_id": "219042",
            }
        },
    )
    monkeypatch.setattr(
        "api.portfolio_service._attach_lot_outlook",
        lambda lots, encodings=None: lots,
    )

    rows = enrich_lots(
        [
            {
                "card_id": "sv3-1",
                "quantity": 2,
                "purchase_price": 8.0,
                "condition": "LP",
                "printing": "Normal",
                "status": "open",
            }
        ]
    )
    lot = rows[0]
    assert lot["spot_source"] == "justtcg_variant"
    assert abs(float(lot["market_price"]) - 11.0) < 1e-9
    assert abs(float(lot["market_value"]) - 22.0) < 1e-9
    # Fair/predicted still uses NM×multiplier (22 * 0.85).
    assert abs(float(lot["predicted_price"]) - 18.7) < 1e-9

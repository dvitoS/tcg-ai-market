"""pokemontcg.io single-card fetch used by live price resolution."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests


def test_fetch_pokemon_card_returns_data(monkeypatch):
    import pokemon_tcg_client as pokemon

    monkeypatch.setattr(
        pokemon,
        "_pokemon_get",
        lambda url, params, progress=None: {"data": {"id": "sv3-1", "name": "Pikachu"}},
    )
    data = pokemon.fetch_pokemon_card("sv3-1")
    assert data["id"] == "sv3-1"


def test_fetch_pokemon_card_404_returns_none(monkeypatch):
    import pokemon_tcg_client as pokemon

    response = MagicMock()
    response.status_code = 404

    def boom(*args, **kwargs):
        raise requests.HTTPError("404", response=response)

    monkeypatch.setattr(pokemon, "_pokemon_get", boom)
    assert pokemon.fetch_pokemon_card("missing-1", quiet=True) is None


def test_resolve_tcgplayer_id_uses_fetch_pokemon_card(monkeypatch):
    import database as db_mod
    import services.live_prices as live

    card = MagicMock()
    card.tcgplayer_id = None
    card.name = "Pikachu"
    card.set_name = "151"
    monkeypatch.setattr(db_mod, "get_card", lambda cid: card)
    monkeypatch.setattr(db_mod, "update_card_tcgplayer_id", lambda *a, **k: None)
    monkeypatch.setattr(
        "api_client.fetch_pokemon_card",
        lambda cid, quiet=True: {"tcgplayer": {"url": "https://www.tcgplayer.com/product/12345"}},
    )
    monkeypatch.setattr(
        "justtcg_client.extract_tcgplayer_product_id",
        lambda payload: "12345",
    )

    assert live.resolve_tcgplayer_id("sv3-1") == "12345"

"""CAT.2b — TCGdex catalog fallback keeps Soft Ink pokemontcg ids."""

from __future__ import annotations

from tcgdex_client import (
    tcgdex_local_to_pokemontcg_id,
    tcgdex_set_card_rows_as_pokemontcg,
    unpad_local_id,
)


def test_unpad_local_id() -> None:
    assert unpad_local_id("001") == "1"
    assert unpad_local_id("025") == "25"
    assert unpad_local_id("TG01") == "TG1"
    assert unpad_local_id("H29") == "H29"


def test_tcgdex_local_to_soft_id() -> None:
    assert tcgdex_local_to_pokemontcg_id("sv1", "001") == "sv1-1"
    assert tcgdex_local_to_pokemontcg_id("sv3pt5", "025") == "sv3pt5-25"
    assert tcgdex_local_to_pokemontcg_id("me3", "004") == "me3-4"


def test_tcgdex_set_rows_as_pokemontcg_shape(monkeypatch) -> None:
    def fake_get(path: str, *, timeout: float = 45.0):
        assert path == "sets/sv01"
        return {
            "id": "sv01",
            "name": "Scarlet & Violet",
            "cards": [
                {
                    "id": "sv01-001",
                    "localId": "001",
                    "name": "Pineco",
                    "image": "https://assets.tcgdex.net/en/sv/sv01/001",
                },
                {
                    "id": "sv01-025",
                    "localId": "025",
                    "name": "Pikachu",
                    "image": "https://assets.tcgdex.net/en/sv/sv01/025",
                },
            ],
        }

    monkeypatch.setattr("tcgdex_client._tcgdex_get", fake_get)
    rows = tcgdex_set_card_rows_as_pokemontcg("sv1", set_name="Scarlet & Violet")
    assert [r["id"] for r in rows] == ["sv1-1", "sv1-25"]
    assert rows[0]["name"] == "Pineco"
    assert rows[0]["set"]["id"] == "sv1"
    assert rows[0]["images"]["large"].endswith("/high.webp")
    assert rows[0]["_source"] == "tcgdex"


def test_fetch_cards_uses_tcgdex_when_pokemontcg_empty(monkeypatch) -> None:
    import pokemon_tcg_client as pokemon

    monkeypatch.setenv("NIGHTLY_TCGDEX_FALLBACK", "1")
    monkeypatch.setattr(pokemon, "rate_limit_sleep_seconds", lambda: 0)

    def boom(*_a, **_k):
        raise RuntimeError("pokemontcg down")

    monkeypatch.setattr(pokemon, "fetch_cards_for_set", boom)
    monkeypatch.setattr(
        "tcgdex_client.tcgdex_set_card_rows_as_pokemontcg",
        lambda sid, set_name=None: [
            {
                "id": f"{sid}-1",
                "name": "Demo",
                "set": {"id": sid, "name": set_name or sid},
                "images": {"small": "x", "large": "y"},
                "_source": "tcgdex",
            }
        ],
    )
    cards = pokemon.fetch_cards(set_ids=[("sv1", "Scarlet & Violet")], paginate=True)
    assert len(cards) == 1
    assert cards[0]["id"] == "sv1-1"
    assert cards[0]["_source"] == "tcgdex"


def test_fallback_can_be_disabled(monkeypatch) -> None:
    import pokemon_tcg_client as pokemon

    monkeypatch.setenv("NIGHTLY_TCGDEX_FALLBACK", "0")
    monkeypatch.setattr(pokemon, "rate_limit_sleep_seconds", lambda: 0)
    monkeypatch.setattr(
        pokemon,
        "fetch_cards_for_set",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("down")),
    )
    called = {"n": 0}

    def should_not_run(*_a, **_k):
        called["n"] += 1
        return []

    monkeypatch.setattr(
        "tcgdex_client.tcgdex_set_card_rows_as_pokemontcg",
        should_not_run,
    )
    cards = pokemon.fetch_cards(set_ids=[("sv1", "SV")], paginate=True)
    assert cards == []
    assert called["n"] == 0

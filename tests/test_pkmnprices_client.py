"""Unit tests for PkmnPrices client (mocked HTTP — no live key)."""

from __future__ import annotations

import pkmnprices_client as client


def setup_function() -> None:
    client.clear_pkmnprices_cache()
    client.reset_pkmnprices_request_count()


def test_pkmn_api_key_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("PKMN_API_KEY", " pk-test-key ")
    monkeypatch.setattr(
        "config.get_pkmn_api_key",
        lambda: "pk-test-key",
    )
    assert client.pkmn_api_key() == "pk-test-key"
    assert client.pkmnprices_configured() is True


def test_find_card_id_by_tcgplayer_id(monkeypatch) -> None:
    monkeypatch.setattr(client, "pkmn_api_key", lambda: "pk-test")

    def _fake_get(path, params=None):
        assert path == "/v1/cards"
        assert params["tcg_player_id"] == 12345
        return {"data": [{"id": 99, "name": "Pikachu"}]}

    monkeypatch.setattr(client, "_get", _fake_get)
    assert client.find_card_id_by_tcgplayer_id("12345") == 99
    assert client.find_card_id_by_tcgplayer_id("abc") is None


def test_nm_history_for_tcgplayer_id(monkeypatch) -> None:
    monkeypatch.setattr(client, "pkmn_api_key", lambda: "pk-test")
    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", lambda _tcp: 7)

    def _fake_get(path, params=None):
        assert path == "/v1/cards/7/prices/history"
        assert params["condition"] == "Near Mint"
        return {
            "data": [
                {
                    "date": "2024-02-02",
                    "avg": 12.5,
                    "condition": "Near Mint",
                    "source": "tcgplayer",
                },
                {
                    "date": "2024-02-01T00:00:00Z",
                    "avg": 11.0,
                    "condition": "Near Mint",
                    "source": "tcgplayer",
                },
                {
                    "date": "2024-02-01",
                    "avg": 99.0,
                    "condition": "Lightly Played",
                    "source": "tcgplayer",
                },
            ]
        }

    monkeypatch.setattr(client, "_get", _fake_get)
    rows = client.nm_history_for_tcgplayer_id("555")
    assert rows == [
        {"date": "2024-02-01", "price": 11.0},
        {"date": "2024-02-02", "price": 12.5},
    ]


def test_nm_spot_prefers_holofoil(monkeypatch) -> None:
    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", lambda _tcp: 3)
    monkeypatch.setattr(
        client,
        "get_card",
        lambda _id, currency="usd": {
            "prices": [
                {
                    "currency": "USD",
                    "condition": "Near Mint",
                    "variant": "Normal",
                    "market_price": 5.0,
                    "source": "tcgplayer",
                },
                {
                    "currency": "USD",
                    "condition": "Near Mint",
                    "variant": "Holofoil",
                    "market_price": 8.0,
                    "source": "tcgplayer",
                },
            ]
        },
    )
    assert client.nm_spot_for_tcgplayer_id(3) == 8.0

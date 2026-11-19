"""JustTCG nightly prefers tcgplayer_id batches over set walks."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import sync_justtcg as sync


def test_batch_path_updates_without_set_catalog(monkeypatch):
    card = SimpleNamespace(
        id="sv8-1",
        name="Pikachu",
        set_name="Surging Sparks",
        tcgplayer_id="999001",
        market_price=10.0,
    )
    monkeypatch.setattr(sync, "justtcg_api_key", lambda: "key")
    monkeypatch.setattr(sync, "init_db", lambda: None)
    monkeypatch.setattr(sync, "_index_db_cards", lambda: {"sv8": [("1", card)]})
    monkeypatch.setattr(sync, "distinct_history_card_ids", lambda: set())
    monkeypatch.setattr(sync, "_known_unmatched_set_codes", lambda: set())
    monkeypatch.setattr(sync, "list_cards_for_sync", lambda limit=None: [card])
    monkeypatch.setattr(sync, "table_count", lambda _t: 0)
    monkeypatch.setattr(sync, "justtcg_request_count", lambda: 1)

    calls = {"sets": 0, "batch": 0}

    def fake_batch(ids):
        calls["batch"] += 1
        assert ids == ["999001"]
        return [
            {
                "tcgplayerId": "999001",
                "number": "1",
                "variants": [
                    {
                        "condition": "Near Mint",
                        "price": 12.5,
                        "priceHistory": [
                            {"date": f"2026-10-{d:02d}", "price": 12.0 + d * 0.1}
                            for d in range(1, 15)
                        ],
                    }
                ],
            }
        ]

    monkeypatch.setattr(sync, "batch_by_tcgplayer_ids", fake_batch)
    monkeypatch.setattr(
        sync,
        "list_pokemon_sets",
        lambda: (_ for _ in ()).throw(AssertionError("set catalog should not run")),
    )
    monkeypatch.setattr(sync, "replace_card_history", lambda *_a, **_k: 14)
    monkeypatch.setattr(sync, "update_card_market_price", lambda *_a, **_k: None)

    with patch.object(sync, "fetch_set_cards_page") as fetch_sets:
        stats = sync.sync_justtcg_price_history(limit=10)

    assert stats["updated"] == 1
    assert stats["batch_updated"] == 1
    assert calls["batch"] == 1
    fetch_sets.assert_not_called()


def test_pkmn_fallback_on_justtcg_empty(monkeypatch):
    card = SimpleNamespace(
        id="sv8-2",
        name="Charmander",
        set_name="Surging Sparks",
        tcgplayer_id="999002",
        market_price=3.0,
    )
    monkeypatch.setattr(sync, "justtcg_api_key", lambda: "key")
    monkeypatch.setattr(sync, "init_db", lambda: None)
    monkeypatch.setattr(sync, "_index_db_cards", lambda: {"sv8": [("2", card)]})
    monkeypatch.setattr(sync, "distinct_history_card_ids", lambda: set())
    monkeypatch.setattr(sync, "_known_unmatched_set_codes", lambda: set())
    monkeypatch.setattr(sync, "list_cards_for_sync", lambda limit=None: [card])
    monkeypatch.setattr(sync, "table_count", lambda _t: 0)
    monkeypatch.setattr(sync, "justtcg_request_count", lambda: 1)
    monkeypatch.setattr(sync, "pkmn_nightly_card_budget", lambda: 50)
    monkeypatch.setattr(
        sync,
        "batch_by_tcgplayer_ids",
        lambda ids: [
            {
                "tcgplayerId": "999002",
                "number": "2",
                "variants": [{"condition": "Near Mint", "price": None, "priceHistory": []}],
            }
        ],
    )
    monkeypatch.setattr(
        sync,
        "list_pokemon_sets",
        lambda: (_ for _ in ()).throw(AssertionError("set catalog should not run")),
    )

    pkmn_calls = {"n": 0}

    def fake_pkmn(tcp, **_kwargs):
        pkmn_calls["n"] += 1
        assert str(tcp) == "999002"
        return [{"date": f"2026-10-{d:02d}", "price": 3.0 + d * 0.05} for d in range(1, 15)]

    monkeypatch.setattr("pkmnprices_client.pkmnprices_configured", lambda: True)
    monkeypatch.setattr("pkmnprices_client.nm_history_for_tcgplayer_id", fake_pkmn)
    monkeypatch.setattr(sync, "replace_card_history", lambda *_a, **_k: 14)
    monkeypatch.setattr(sync, "update_card_market_price", lambda *_a, **_k: None)

    with patch.object(sync, "fetch_set_cards_page") as fetch_sets:
        stats = sync.sync_justtcg_price_history(limit=10)

    assert pkmn_calls["n"] == 1
    assert stats["updated"] == 1
    assert stats["pkmn_updated"] == 1
    assert stats["batch_updated"] == 0
    fetch_sets.assert_not_called()


def test_pkmn_not_called_when_justtcg_ok(monkeypatch):
    card = SimpleNamespace(
        id="sv8-3",
        name="Squirtle",
        set_name="Surging Sparks",
        tcgplayer_id="999003",
        market_price=4.0,
    )
    monkeypatch.setattr(sync, "justtcg_api_key", lambda: "key")
    monkeypatch.setattr(sync, "init_db", lambda: None)
    monkeypatch.setattr(sync, "_index_db_cards", lambda: {"sv8": [("3", card)]})
    monkeypatch.setattr(sync, "distinct_history_card_ids", lambda: set())
    monkeypatch.setattr(sync, "_known_unmatched_set_codes", lambda: set())
    monkeypatch.setattr(sync, "list_cards_for_sync", lambda limit=None: [card])
    monkeypatch.setattr(sync, "table_count", lambda _t: 0)
    monkeypatch.setattr(sync, "justtcg_request_count", lambda: 1)
    monkeypatch.setattr(sync, "pkmn_nightly_card_budget", lambda: 50)

    def fake_batch(ids):
        return [
            {
                "tcgplayerId": "999003",
                "number": "3",
                "variants": [
                    {
                        "condition": "Near Mint",
                        "price": 5.0,
                        "priceHistory": [
                            {"date": f"2026-10-{d:02d}", "price": 4.5 + d * 0.1}
                            for d in range(1, 15)
                        ],
                    }
                ],
            }
        ]

    monkeypatch.setattr(sync, "batch_by_tcgplayer_ids", fake_batch)
    monkeypatch.setattr(
        sync,
        "list_pokemon_sets",
        lambda: (_ for _ in ()).throw(AssertionError("set catalog should not run")),
    )

    def boom(*_a, **_k):
        raise AssertionError("PkmnPrices must not run when JustTCG succeeds")

    monkeypatch.setattr("pkmnprices_client.pkmnprices_configured", boom)
    monkeypatch.setattr(sync, "replace_card_history", lambda *_a, **_k: 14)
    monkeypatch.setattr(sync, "update_card_market_price", lambda *_a, **_k: None)

    stats = sync.sync_justtcg_price_history(limit=10)
    assert stats["updated"] == 1
    assert stats["batch_updated"] == 1
    assert stats.get("pkmn_updated", 0) == 0


def test_pkmn_fallback_when_tcp_missing_from_batch(monkeypatch):
    card = SimpleNamespace(
        id="sv8-4",
        name="Bulbasaur",
        set_name="Surging Sparks",
        tcgplayer_id="999004",
        market_price=2.0,
    )
    monkeypatch.setattr(sync, "justtcg_api_key", lambda: "key")
    monkeypatch.setattr(sync, "init_db", lambda: None)
    monkeypatch.setattr(sync, "_index_db_cards", lambda: {"sv8": [("4", card)]})
    monkeypatch.setattr(sync, "distinct_history_card_ids", lambda: set())
    monkeypatch.setattr(sync, "_known_unmatched_set_codes", lambda: set())
    monkeypatch.setattr(sync, "list_cards_for_sync", lambda limit=None: [card])
    monkeypatch.setattr(sync, "table_count", lambda _t: 0)
    monkeypatch.setattr(sync, "justtcg_request_count", lambda: 1)
    monkeypatch.setattr(sync, "pkmn_nightly_card_budget", lambda: 50)
    monkeypatch.setattr(sync, "batch_by_tcgplayer_ids", lambda ids: [])
    monkeypatch.setattr(
        sync,
        "list_pokemon_sets",
        lambda: (_ for _ in ()).throw(AssertionError("set catalog should not run")),
    )
    monkeypatch.setattr("pkmnprices_client.pkmnprices_configured", lambda: True)
    monkeypatch.setattr(
        "pkmnprices_client.nm_history_for_tcgplayer_id",
        lambda *_a, **_k: [
            {"date": f"2026-09-{d:02d}", "price": 2.0 + d * 0.1} for d in range(1, 12)
        ],
    )
    monkeypatch.setattr(sync, "replace_card_history", lambda *_a, **_k: 11)
    monkeypatch.setattr(sync, "update_card_market_price", lambda *_a, **_k: None)

    stats = sync.sync_justtcg_price_history(limit=10)
    assert stats["pkmn_updated"] == 1
    assert stats["updated"] == 1

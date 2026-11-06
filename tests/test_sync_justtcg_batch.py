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

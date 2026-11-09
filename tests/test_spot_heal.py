"""Spot heal — unstick poisoned JustTCG tips without mass wipe."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from services.spot_heal import heal_poisoned_spots, poisoned_card_ids_from_board
import sync_justtcg as sync


def _poison_board(n: int = 12) -> pd.DataFrame:
    sets = ["Cosmic Eclipse", "Unified Minds", "Vivid Voltage", "Paldean Fates"]
    rows = []
    for i in range(n):
        rows.append(
            {
                "id": f"poison-{i}",
                "name": f"Card {i}",
                "set_name": sets[i % len(sets)],
                "rarity": "Common" if i % 3 else "Rare",
                "price": 68.15,
                "market_price": 68.15,
                "confidence_ok": True,
                "signal": "BUY",
            }
        )
    for i in range(15):
        rows.append(
            {
                "id": f"bulk-{i}",
                "name": f"Bulk {i}",
                "set_name": sets[i % len(sets)],
                "rarity": "Common",
                "price": 0.25,
                "market_price": 0.25,
                "confidence_ok": True,
                "signal": "BUY",
            }
        )
    rows.append(
        {
            "id": "ok-1",
            "name": "Charizard",
            "set_name": "Base",
            "rarity": "Rare Holo",
            "price": 200.0,
            "market_price": 200.0,
            "confidence_ok": True,
            "signal": "BUY",
        }
    )
    return pd.DataFrame(rows)


def test_detect_poisoned_ids_from_board() -> None:
    board = _poison_board()
    ids, keys = poisoned_card_ids_from_board(board)
    assert set(ids) == {f"poison-{i}" for i in range(12)}
    assert 68.15 in keys
    assert "bulk-0" not in ids
    assert "ok-1" not in ids


def test_dry_run_writes_nothing(monkeypatch) -> None:
    board = _poison_board()
    monkeypatch.setattr(
        "services.spot_heal.detect_poisoned_card_ids",
        lambda: poisoned_card_ids_from_board(board),
    )
    calls: list[str] = []
    monkeypatch.setattr(
        "database.clear_card_market_prices",
        lambda ids: (calls.extend(f"null:{cid}" for cid in ids), len(list(ids)))[1],
    )
    monkeypatch.setattr(
        "database.delete_card_history",
        lambda cid: calls.append(f"del:{cid}"),
    )
    out = heal_poisoned_spots(mode="dry_run", limit=5)
    assert out["count"] == 5
    assert set(out["ids"]).issubset({f"poison-{i}" for i in range(12)})
    assert calls == []


def test_null_market_only_poisoned(monkeypatch) -> None:
    board = _poison_board()
    monkeypatch.setattr(
        "services.spot_heal.detect_poisoned_card_ids",
        lambda: poisoned_card_ids_from_board(board),
    )
    nulled: list[str] = []
    quarantined: list[str] = []

    def fake_clear(ids):
        nulled.extend(ids)
        return len(list(ids))

    import database as db

    monkeypatch.setattr(db, "clear_card_market_prices", fake_clear)
    monkeypatch.setattr(
        "services.quotes_store.quarantine_market_quote_ids",
        lambda ids: (quarantined.extend(ids), len(list(ids)))[1],
    )
    out = heal_poisoned_spots(mode="null_market", limit=4)
    assert out["nulled"] == 4
    assert set(nulled).issubset({f"poison-{i}" for i in range(12)})
    assert out["history_cleared"] == 0
    assert out["quotes_quarantined"] == 4
    assert set(quarantined) == set(nulled)


def test_targeted_null_market_skips_board_scan(monkeypatch) -> None:
    """Per-row sniff Heal must not load the full board (that made clicks feel stuck)."""
    scanned = {"n": 0}

    def boom():
        scanned["n"] += 1
        raise AssertionError("full-board poison detect must not run for targeted null_market")

    monkeypatch.setattr("services.spot_heal.detect_poisoned_card_ids", boom)
    monkeypatch.setattr(
        "services.spot_heal._spot_keys_for_card_ids",
        lambda ids: (_ for _ in ()).throw(AssertionError("spot keys unused for null_market")),
    )
    monkeypatch.setattr("database.clear_card_market_prices", lambda ids: len(list(ids)))
    monkeypatch.setattr(
        "services.quotes_store.quarantine_market_quote_ids",
        lambda ids: len(list(ids)),
    )
    out = heal_poisoned_spots(mode="null_market", card_ids=["sv8-oshawott"])
    assert out["count"] == 1
    assert out["nulled"] == 1
    assert out["quotes_quarantined"] == 1
    assert out["poison_keys"] == []
    assert scanned["n"] == 0


def test_targeted_card_ids_ban_own_spots(monkeypatch) -> None:
    """Isolated wrong tips (Espeon $125) must ban their own key, not only clusters."""
    board = _poison_board(n=10)
    monkeypatch.setattr(
        "services.spot_heal.detect_poisoned_card_ids",
        lambda: poisoned_card_ids_from_board(board),
    )
    monkeypatch.setattr(
        "services.spot_heal._spot_keys_for_card_ids",
        lambda ids: {125.0, 79.5, 9.73},
    )
    monkeypatch.setattr("database.clear_card_market_prices", lambda ids: len(list(ids)))
    monkeypatch.setattr("database.delete_card_history", lambda cid: None)
    monkeypatch.setattr(
        "services.quotes_store.quarantine_market_quote_ids",
        lambda ids: len(list(ids)),
    )
    forbid: dict[str, object] = {}

    def fake_sync(ids, forbid_spot_keys=None):
        forbid["keys"] = set(forbid_spot_keys or [])
        return {
            "updated": 0,
            "skipped": 0,
            "saved": 0,
            "skip_poison": len(ids),
            "skip_absurd": 0,
            "justtcg_requests": 0,
            "with_tcgplayer_id": len(ids),
        }

    monkeypatch.setattr("sync_justtcg.sync_justtcg_for_card_ids", fake_sync)
    out = heal_poisoned_spots(
        mode="refetch",
        card_ids=["dp7-espeon", "sv8-oshawott", "sv8-patrat"],
    )
    assert out["count"] == 3
    assert out["quotes_quarantined"] == 3
    assert {125.0, 79.5, 9.73}.issubset(set(out["poison_keys"]))
    assert {125.0, 79.5, 9.73}.issubset(forbid["keys"])


def test_ingest_blocks_same_poison_key() -> None:
    card = SimpleNamespace(id="sm12-27", market_price=None, tcgplayer_id="1")
    row = {
        "variants": [
            {
                "condition": "Near Mint",
                "price": 68.15,
                "priceHistory": [
                    {"date": f"2026-10-{d:02d}", "price": 68.15} for d in range(1, 15)
                ],
            }
        ],
    }
    updates: list[float] = []
    with patch.object(sync, "update_card_market_price", lambda *_a, **_k: updates.append(1)), patch.object(
        sync, "replace_card_history", lambda *_a, **_k: 14
    ):
        status, written = sync._ingest_card_row(
            card,
            row,
            have_history=set(),
            matched_ids=set(),
            forbid_spot_keys={68.15},
        )
    assert status == "skip_poison"
    assert written == 0
    assert updates == []


def test_ingest_recovers_after_null_prior() -> None:
    card = SimpleNamespace(id="sm12-27", market_price=None, tcgplayer_id="1")
    # JustTCG history uses {p,t} unix timestamps — date/price pairs are ignored.
    base_ts = 1_725_000_000
    row = {
        "variants": [
            {
                "condition": "Near Mint",
                "price": 1.80,
                "priceHistory": [
                    {"p": 1.70 + d * 0.01, "t": base_ts + d * 86400} for d in range(1, 15)
                ],
            }
        ],
    }
    wrote: dict[str, object] = {}
    with patch.object(
        sync,
        "update_card_market_price",
        lambda cid, price, **_k: wrote.setdefault("price", price),
    ), patch.object(
        sync,
        "replace_card_history",
        lambda cid, points: (wrote.setdefault("hist", len(points)), len(points))[1],
    ):
        status, written = sync._ingest_card_row(
            card,
            row,
            have_history=set(),
            matched_ids=set(),
            forbid_spot_keys={68.15},
        )
    assert status == "ok"
    assert written >= 14
    assert wrote["price"] == 1.80


def test_sweep_desk_poison_drains_until_clean(monkeypatch) -> None:
    from services.spot_heal import sweep_desk_poison

    calls = {"auto": 0, "poison": 0}

    def fake_auto(*, mode="null_market", limit=None):
        calls["auto"] += 1
        # First round finds tips; second is clean.
        n = 12 if calls["auto"] == 1 else 0
        return {
            "mode": mode,
            "count": n,
            "quotes_quarantined": n,
            "poison_keys": [68.15] if n else [],
        }

    def fake_poison(*, mode="null_market", limit=None, card_ids=None):
        calls["poison"] += 1
        n = 8 if calls["poison"] == 1 else 0
        return {
            "mode": mode,
            "count": n,
            "quotes_quarantined": n,
            "poison_keys": [99.99] if n else [],
        }

    monkeypatch.setattr("services.spot_heal.heal_auto_unsafe_spots", fake_auto)
    monkeypatch.setattr("services.spot_heal.heal_poisoned_spots", fake_poison)
    out = sweep_desk_poison(max_rounds=4)
    assert out["auto_quarantined"] == 12
    assert out["poison_nulled"] == 8
    assert out["quotes_quarantined"] == 20
    assert 68.15 in out["poison_keys"] and 99.99 in out["poison_keys"]
    assert calls["auto"] == 2
    assert calls["poison"] == 2


def test_verify_top_under_spots_refetches_share_safe(monkeypatch) -> None:
    from services.spot_heal import verify_top_under_spots

    monkeypatch.setenv("NIGHTLY_UNDER_VERIFY_LIMIT", "3")
    monkeypatch.setattr(
        "api.radar_service.build_radar",
        lambda **_k: {
            "under_total": 40,
            "underpriced": [
                {"id": "a-1"},
                {"id": "a-2"},
                {"id": "a-3"},
                {"id": "a-4"},
            ],
        },
    )
    seen: dict[str, object] = {}

    def fake_heal(*, mode, limit=None, card_ids=None):
        seen["mode"] = mode
        seen["limit"] = limit
        seen["ids"] = list(card_ids or [])
        return {
            "mode": mode,
            "count": len(card_ids or []),
            "ids": list(card_ids or []),
            "updated": 1,
            "skip_poison": 2,
        }

    monkeypatch.setattr("services.spot_heal.heal_poisoned_spots", fake_heal)
    out = verify_top_under_spots()
    assert seen["mode"] == "refetch"
    assert seen["ids"] == ["a-1", "a-2", "a-3"]
    assert out["under_total"] == 40
    assert out["skip_poison"] == 2


def test_refetch_never_calls_mass_wipe(monkeypatch) -> None:
    board = _poison_board(n=10)
    monkeypatch.setattr(
        "services.spot_heal.detect_poisoned_card_ids",
        lambda: poisoned_card_ids_from_board(board),
    )
    import database as db

    wiped = {"n": 0}
    monkeypatch.setattr(db, "clear_card_market_prices", lambda ids: len(list(ids)))
    monkeypatch.setattr(db, "delete_card_history", lambda cid: None)

    def boom() -> None:
        wiped["n"] += 1
        raise AssertionError("mass wipe must not run")

    monkeypatch.setattr(db, "clear_price_history", boom)
    monkeypatch.setattr(
        "services.quotes_store.quarantine_market_quote_ids",
        lambda ids: len(list(ids)),
    )
    monkeypatch.setattr(
        "sync_justtcg.sync_justtcg_for_card_ids",
        lambda ids, forbid_spot_keys=None: {
            "updated": 0,
            "skipped": 0,
            "saved": 0,
            "skip_poison": len(ids),
            "skip_absurd": 0,
            "justtcg_requests": 0,
            "with_tcgplayer_id": len(ids),
        },
    )
    out = heal_poisoned_spots(mode="refetch", limit=10)
    assert out["count"] == 10
    assert wiped["n"] == 0
    assert out["skip_poison"] == 10
    assert out["quotes_quarantined"] == 10

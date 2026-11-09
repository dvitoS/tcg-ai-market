"""G0 spot sniff — TCP + eBay auto verdict + optional auto-heal."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.deps import optional_user
from api.main import app
from services import spot_sniff


def _fake_radar(**_kwargs):
    return {
        "source": "demo",
        "underpriced": [
            {
                "id": f"u{i}",
                "name": f"Under {i}",
                "set_name": "Demo",
                "rarity": "Rare",
                "spot": 10 + i,
                "fair_price": 20 + i,
                "edge_pct": 30.0,
                "tcgplayer_id": str(500000 + i),
            }
            for i in range(12)
        ],
        "overpriced": [
            {
                "id": f"o{i}",
                "name": f"Over {i}",
                "set_name": "Demo",
                "rarity": "Rare",
                "spot": 40 + i,
                "fair_price": 20 + i,
                "edge_pct": -25.0,
                "tcgplayer_id": str(600000 + i),
            }
            for i in range(12)
        ],
    }


def test_build_spot_sniff_pack_balances_sides(monkeypatch) -> None:
    monkeypatch.setattr("api.radar_service.build_radar", _fake_radar)
    pack = spot_sniff.build_spot_sniff_pack(
        limit=20, live_check=False, ebay_check=False, auto_heal=False
    )
    assert pack["pass_required"] is True
    assert pack["count"] == 20
    assert pack["under_n"] == 10
    assert pack["over_n"] == 10
    assert pack["items"][0]["tcgplayer_url"].startswith("https://www.tcgplayer.com/product/")
    assert pack["live_checked"] is False
    assert pack["ebay_checked"] is False


def test_combine_verdict_matrix() -> None:
    assert spot_sniff._combine_verdict("ok", "ok") == "pass"
    assert spot_sniff._combine_verdict("ok", "skip", ebay_usable=True) == "review"
    assert spot_sniff._combine_verdict("ok", "skip", ebay_usable=False) == "pass"
    assert spot_sniff._combine_verdict("warn", "ok") == "review"
    assert spot_sniff._combine_verdict("fail", "ok") == "fail"
    assert spot_sniff._combine_verdict("ok", "fail") == "fail"


def test_resolve_missing_tcp_ids(monkeypatch) -> None:
    items = [
        {
            "card_id": "dp45-1",
            "name": "Arceus LV.X",
            "set_name": "DP Black Star Promos",
            "tcgplayer_id": None,
            "tcgplayer_url": None,
        }
    ]

    def _search(**_kwargs):
        return {
            "name": "Arceus LV.X",
            "number": "1",
            "set_name": "DP Black Star Promos",
            "tcgplayer_id": "123456",
            "variants": [
                {
                    "condition": "Near Mint",
                    "printing": "Normal",
                    "markets": [{"region": "NA", "price": 100.0, "price_status": "current"}],
                }
            ],
        }

    monkeypatch.setattr("justtcg_client.search_pokemon_card", _search)
    stats = spot_sniff._resolve_missing_tcp_ids(items)
    assert stats["tcp_missing"] == 1
    assert stats["tcp_resolved"] == 1
    assert items[0]["tcgplayer_id"] == "123456"
    assert items[0]["tcp_live"] == 100.0
    assert items[0]["tcp_match_score"] >= 120
    assert "tcgplayer.com/product/123456" in (items[0]["tcgplayer_url"] or "")


def test_weak_resolved_match_not_auto_fail() -> None:
    items = [
        {
            "card_id": "x-1",
            "name": "Weak",
            "tcp_status": "fail",
            "ebay_status": "skip",
            "tcp_resolved": True,
            "tcp_match_score": 120,
            "notes": "",
        }
    ]
    counts = spot_sniff._apply_verdicts(items, ebay_usable=False)
    assert counts["fail"] == 0
    assert counts["review"] == 1
    assert items[0]["verdict"] == "review"


def test_reject_weak_tcp_search(monkeypatch) -> None:
    items = [
        {
            "card_id": "sv1-1",
            "name": "Pikachu",
            "set_name": "Scarlet & Violet",
            "tcgplayer_id": None,
        }
    ]

    def _search(**_kwargs):
        # Wrong card — name mismatch, no number → low score
        return {
            "name": "Pikachu VMAX",
            "number": "999",
            "set_name": "Other",
            "tcgplayer_id": "999",
            "variants": [],
        }

    monkeypatch.setattr("justtcg_client.search_pokemon_card", _search)
    stats = spot_sniff._resolve_missing_tcp_ids(items)
    assert stats["tcp_resolved"] == 0
    assert stats["tcp_rejected"] == 1
    assert items[0].get("tcgplayer_id") in (None, "")
    assert items[0]["skip_reason"] == "weak_tcp_match"


def test_pct_delta_helpers() -> None:
    assert spot_sniff._pct_delta(110, 100) == 10.0
    assert spot_sniff._band_status(spot=110, live=100, delta_pct=10.0) == "ok"
    assert spot_sniff._band_status(spot=130, live=100, delta_pct=30.0) == "warn"
    assert spot_sniff._band_status(spot=150, live=100, delta_pct=50.0) == "fail"
    assert spot_sniff._band_status(spot=10, live=None, delta_pct=None) == "skip"


def test_live_and_ebay_pass_and_auto_heal_fail(monkeypatch) -> None:
    monkeypatch.setattr("api.radar_service.build_radar", _fake_radar)

    def _batch(ids):
        out = []
        for tid in ids:
            if tid.startswith("5"):
                idx = int(tid) - 500000
                spot = 10 + idx
                # u0 wildly wrong → TCP fail
                live = 50.0 if tid == "500000" else float(spot)
            else:
                idx = int(tid) - 600000
                spot = 40 + idx
                live = float(spot)
            out.append(
                {
                    "tcgplayer_id": tid,
                    "variants": [
                        {
                            "condition": "Near Mint",
                            "printing": "Normal",
                            "markets": [
                                {"region": "NA", "price": live, "price_status": "current"}
                            ],
                        }
                    ],
                }
            )
        return out

    def _ebay(*, card_id, name, set_name, limit=6):
        # Match spot for everyone except leave true sold so eBay ok.
        # Parse spot from card id u{i}/o{i}
        if card_id.startswith("u"):
            spot = 10 + int(card_id[1:])
        else:
            spot = 40 + int(card_id[1:])
        stats = {"min": spot, "median": spot, "max": spot, "n": 3.0, "is_sold": 1.0}
        rows = [{"price": spot, "is_sold": True}]
        return rows, None, stats

    healed: list[str] = []

    def _heal(*, mode, limit=None, card_ids=None):
        ids = list(card_ids or [])
        healed.extend(ids)
        return {
            "mode": mode,
            "ids": ids,
            "count": len(ids),
            "nulled": len(ids),
            "quotes_quarantined": len(ids),
        }

    monkeypatch.setattr("justtcg_client.justtcg_api_key", lambda: "test-key")
    monkeypatch.setattr("justtcg_client.batch_by_tcgplayer_ids", _batch)
    monkeypatch.setattr("justtcg_client.JUSTTCG_BATCH_SIZE", 40)
    monkeypatch.setattr("ebay_client.ebay_configured", lambda: True)
    monkeypatch.setattr(
        "services.ebay_listings.fetch_ebay_sold_comps",
        _ebay,
    )
    monkeypatch.setattr("services.spot_heal.heal_poisoned_spots", _heal)

    pack = spot_sniff.build_spot_sniff_pack(
        limit=20, live_check=True, ebay_check=True, auto_heal=True
    )
    assert pack["live_checked"] is True
    assert pack["ebay_checked"] is True
    assert "u0" in pack["healed_ids"]
    assert all(item["card_id"] != "u0" for item in pack["items"])
    assert pack["healed_n"] >= 1
    assert pack["verdict_fail"] == 0
    # Remaining rows should be mostly pass (TCP≈eBay≈spot).
    assert pack["verdict_pass"] >= 15
    assert pack["g0_ready"] is True


def test_sniff_pack_endpoint_ops_only() -> None:
    def _non_ops(_authorization=None):
        return {
            "id": "user-2",
            "email": "random@example.com",
            "dev": False,
            "ops": False,
        }

    app.dependency_overrides[optional_user] = _non_ops
    try:
        client = TestClient(app)
        assert client.get("/api/data-health/sniff-pack").status_code == 403
    finally:
        app.dependency_overrides.pop(optional_user, None)


def test_sniff_pack_endpoint_ok_for_ops(monkeypatch) -> None:
    def _ops(_authorization=None):
        return {
            "id": "ops-1",
            "email": "vito.skender@gmail.com",
            "dev": False,
            "ops": True,
        }

    monkeypatch.setattr(
        "services.spot_sniff.build_spot_sniff_pack",
        lambda limit=20, live_check=True, ebay_check=True, auto_heal=True: {
            "generated_at": "2026-11-08T00:00:00+00:00",
            "limit": limit,
            "count": 0,
            "under_n": 0,
            "over_n": 0,
            "board_source": "empty",
            "pass_required": True,
            "live_checked": False,
            "live_configured": False,
            "auto_ok": 0,
            "auto_warn": 0,
            "auto_fail": 0,
            "auto_skip": 0,
            "tcp_missing": 0,
            "tcp_resolved": 0,
            "live_error": None,
            "ebay_checked": False,
            "ebay_configured": False,
            "ebay_usable": False,
            "ebay_ok": 0,
            "ebay_warn": 0,
            "ebay_fail": 0,
            "ebay_skip": 0,
            "ebay_error": None,
            "verdict_pass": 0,
            "verdict_review": 0,
            "verdict_fail": 0,
            "healed_n": 0,
            "healed_ids": [],
            "g0_ready": False,
            "instructions": "check",
            "items": [],
        },
    )
    monkeypatch.setattr("api.catalog_service.clear_board_cache", lambda: None)
    app.dependency_overrides[optional_user] = _ops
    try:
        client = TestClient(app)
        resp = client.get(
            "/api/data-health/sniff-pack",
            params={"limit": 20, "auto_heal": "true", "ebay_check": "true"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pass_required"] is True
        assert "g0_ready" in body
        assert "verdict_pass" in body
    finally:
        app.dependency_overrides.pop(optional_user, None)

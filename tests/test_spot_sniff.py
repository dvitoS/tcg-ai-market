"""M0.2 / G0 spot sniff pack — sure sample + optional JustTCG live TCP assist."""

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
    pack = spot_sniff.build_spot_sniff_pack(limit=20, live_check=False)
    assert pack["pass_required"] is True
    assert pack["count"] == 20
    assert pack["under_n"] == 10
    assert pack["over_n"] == 10
    assert pack["items"][0]["tcgplayer_url"].startswith("https://www.tcgplayer.com/product/")
    assert pack["items"][0]["kestrel_path"].startswith("/cards/")
    assert pack["live_checked"] is False
    assert pack["auto_skip"] == 20


def test_live_check_flags_fail_and_sorts_first(monkeypatch) -> None:
    monkeypatch.setattr("api.radar_service.build_radar", _fake_radar)

    def _batch(ids):
        # Match first UNDER (spot 10 → tid 500000) as wildly different live price.
        out = []
        for tid in ids:
            live = 50.0 if tid == "500000" else float(tid) % 100 + 5
            # For under 0: spot=10 → live=50 → fail (~-80%)
            # For others: invent live near spot by using name index from tid
            if tid.startswith("5"):
                idx = int(tid) - 500000
                spot = 10 + idx
                live = spot if tid != "500000" else 50.0
            else:
                idx = int(tid) - 600000
                spot = 40 + idx
                live = spot
            out.append(
                {
                    "tcgplayer_id": tid,
                    "variants": [
                        {
                            "condition": "Near Mint",
                            "printing": "Normal",
                            "markets": [{"region": "NA", "price": live, "price_status": "current"}],
                        }
                    ],
                }
            )
        return out

    monkeypatch.setattr("justtcg_client.justtcg_api_key", lambda: "test-key")
    monkeypatch.setattr("justtcg_client.batch_by_tcgplayer_ids", _batch)
    monkeypatch.setattr("justtcg_client.JUSTTCG_BATCH_SIZE", 40)

    pack = spot_sniff.build_spot_sniff_pack(limit=20, live_check=True)
    assert pack["live_checked"] is True
    assert pack["auto_fail"] >= 1
    assert pack["items"][0]["auto_status"] == "fail"
    assert pack["items"][0]["card_id"] == "u0"
    assert pack["items"][0]["tcp_live"] == 50.0


def test_pct_delta_helpers() -> None:
    assert spot_sniff._pct_delta(110, 100) == 10.0
    assert spot_sniff._auto_status(spot=110, live=100, delta_pct=10.0) == "ok"
    assert spot_sniff._auto_status(spot=130, live=100, delta_pct=30.0) == "warn"
    assert spot_sniff._auto_status(spot=150, live=100, delta_pct=50.0) == "fail"
    assert spot_sniff._auto_status(spot=10, live=None, delta_pct=None) == "skip"


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
        lambda limit=20, live_check=True: {
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
            "live_error": None,
            "instructions": "check",
            "items": [],
        },
    )
    monkeypatch.setattr("api.catalog_service.clear_board_cache", lambda: None)
    app.dependency_overrides[optional_user] = _ops
    try:
        client = TestClient(app)
        resp = client.get("/api/data-health/sniff-pack", params={"limit": 20})
        assert resp.status_code == 200
        body = resp.json()
        assert body["pass_required"] is True
        assert "items" in body
        assert "auto_fail" in body
    finally:
        app.dependency_overrides.pop(optional_user, None)

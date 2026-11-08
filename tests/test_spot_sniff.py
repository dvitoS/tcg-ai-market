"""M0.2 spot sniff pack — sure UNDER/OVER sample for manual TCP/eBay checks."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.deps import optional_user
from api.main import app
from services import spot_sniff


def test_build_spot_sniff_pack_balances_sides(monkeypatch) -> None:
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

    monkeypatch.setattr("api.radar_service.build_radar", _fake_radar)
    pack = spot_sniff.build_spot_sniff_pack(limit=20)
    assert pack["pass_required"] is True
    assert pack["count"] == 20
    assert pack["under_n"] == 10
    assert pack["over_n"] == 10
    assert pack["items"][0]["tcgplayer_url"].startswith("https://www.tcgplayer.com/product/")
    assert pack["items"][0]["kestrel_path"].startswith("/cards/")


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
        lambda limit=20: {
            "generated_at": "2026-11-08T00:00:00+00:00",
            "limit": limit,
            "count": 0,
            "under_n": 0,
            "over_n": 0,
            "board_source": "empty",
            "pass_required": True,
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
    finally:
        app.dependency_overrides.pop(optional_user, None)

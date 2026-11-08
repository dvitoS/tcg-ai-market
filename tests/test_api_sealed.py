"""Sealed product quote + ensure (demo seed)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from api.sealed_service import ensure_sealed_card, quote_sealed_products


def test_sealed_quote_demo_seed() -> None:
    client = TestClient(app)
    res = client.get("/api/sealed/quote", params={"q": "etb"})
    assert res.status_code == 200
    body = res.json()
    assert body["source"] in {"demo", "justtcg", "empty"}
    assert "items" in body
    if body["source"] == "demo":
        assert len(body["items"]) >= 1
        assert body["items"][0]["card_id"].startswith("sealed:")
        assert body["items"][0]["kind"] == "sealed"


def test_sealed_quote_showcase_without_query() -> None:
    client = TestClient(app)
    res = client.get("/api/sealed/quote")
    assert res.status_code == 200
    body = res.json()
    assert body["source"] in {"demo", "justtcg"}
    assert len(body["items"]) >= 1
    assert body["items"][0]["card_id"].startswith("sealed:")
    # Showcase uses verified Pokémon TCP ids → CDN art URLs (demo path).
    with_art = [row for row in body["items"] if row.get("image_url")]
    assert len(with_art) >= 1
    known = {
        "565630",
        "600518",
        "593355",
        "502005",
        "528040",
        "557350",
        "543845",
        "532848",
    }
    assert {str(row.get("tcgplayer_id")) for row in body["items"]} <= known
    if body["source"] == "demo":
        assert len(with_art) >= 3
        assert "tcgplayer-cdn.tcgplayer.com" in str(with_art[0]["image_url"])


def test_token_overlap_seed_sniff() -> None:
    from api.sealed_service import _token_overlap

    assert _token_overlap(
        "Prismatic Evolutions Elite Trainer Box (ETB)",
        "SV Prismatic Evolutions Elite Trainer Box",
    )
    assert not _token_overlap(
        "Prismatic Evolutions Elite Trainer Box (ETB)",
        "Magic: The Gathering Collector Booster",
    )


def test_live_showcase_sniff_keeps_matching_seeds(monkeypatch) -> None:
    from api import sealed_service

    monkeypatch.setattr(
        "justtcg_client.justtcg_api_key",
        lambda: "test-key",
    )
    monkeypatch.setattr(sealed_service, "demo_mode", lambda: False)

    def fake_quote(*, tcgplayer_id=None, **_kwargs):
        tid = str(tcgplayer_id or "")
        if tid == "565630":
            return [
                {
                    "card_id": "sealed:565630",
                    "name": "Surging Sparks Elite Trainer Box",
                    "set_name": "Surging Sparks",
                    "tcgplayer_id": "565630",
                    "spot_usd": 51.0,
                    "image_url": None,
                    "source": "justtcg",
                    "kind": "sealed",
                }
            ]
        if tid == "600518":
            return [
                {
                    "card_id": "sealed:600518",
                    "name": "Completely Unrelated MTG Bundle",
                    "set_name": "Wrong",
                    "tcgplayer_id": "600518",
                    "spot_usd": 12.0,
                    "image_url": None,
                    "source": "justtcg",
                    "kind": "sealed",
                }
            ]
        return []

    monkeypatch.setattr("justtcg_sealed.quote_sealed", fake_quote)
    payload = sealed_service.quote_sealed_products(allow_showcase=True, limit=8)
    assert payload["source"] == "justtcg"
    ids = {str(row.get("tcgplayer_id")) for row in payload["items"]}
    assert ids == {"565630"}
    assert payload["items"][0]["image_url"]


def test_normalize_skips_cdn_without_external_tcp() -> None:
    from justtcg_sealed import normalize_sealed_hit

    hit = normalize_sealed_hit(
        {
            "id": "999001",
            "name": "Opaque Sealed Handle",
            "variants": [],
        }
    )
    assert hit is not None
    assert hit["tcgplayer_id"] == "999001"
    # Without external_ids.tcgplayer, do not invent CDN art from opaque ids.
    assert hit["image_url"] is None


def test_tcgplayer_product_image_helper() -> None:
    from justtcg_sealed import tcgplayer_product_image

    assert tcgplayer_product_image("600518") == (
        "https://tcgplayer-cdn.tcgplayer.com/product/600518_in_1000x1000.jpg"
    )
    assert tcgplayer_product_image("demo-x") is None


def test_ensure_sealed_demo() -> None:
    payload = quote_sealed_products(q="etb")
    assert payload["items"]
    hit = payload["items"][0]
    ensured = ensure_sealed_card(hit)
    assert ensured["ensured"] is True
    assert ensured["card_id"].startswith("sealed:")


def test_sealed_ensure_route() -> None:
    client = TestClient(app)
    res = client.post(
        "/api/sealed/ensure",
        json={
            "card_id": "sealed:demo-test",
            "name": "Demo ETB",
            "tcgplayer_id": "demo-test",
            "spot_usd": 40.0,
            "source": "demo",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["card_id"] == "sealed:demo-test"
    assert body["ensured"] is True

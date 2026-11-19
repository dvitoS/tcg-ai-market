"""Market comps bundle — eBay sold + Cardmarket + population."""

from __future__ import annotations

from api.market_comps_service import build_market_comps


def test_build_market_comps_without_pkmn(monkeypatch) -> None:
    monkeypatch.setattr("pkmnprices_client.pkmnprices_configured", lambda: False)
    monkeypatch.setattr(
        "api.market_comps_service._resolve_tcp",
        lambda _cid: ("123", "Pikachu", "Base"),
    )
    out = build_market_comps("base1-58", limit=5)
    assert out["pkmnprices_configured"] is False
    assert out["ebay_sold"] == []
    assert "PKMN_API_KEY" in (out["ebay_error"] or "")


def test_build_market_comps_happy(monkeypatch) -> None:
    monkeypatch.setattr("pkmnprices_client.pkmnprices_configured", lambda: True)
    monkeypatch.setattr(
        "api.market_comps_service._resolve_tcp",
        lambda _cid: ("999", "Umbreon", "Skyridge"),
    )
    monkeypatch.setattr(
        "pkmnprices_client.ebay_sold_listings_for_tcgplayer_id",
        lambda *_a, **_k: [
            {
                "price": 100.0,
                "currency": "USD",
                "date": "2026-11-01",
                "title": "Umbreon",
                "url": "https://ebay.example/1",
                "condition": "Near Mint",
                "graded": False,
            },
            {
                "price": 120.0,
                "currency": "USD",
                "date": "2026-11-02",
                "title": "Umbreon",
                "url": None,
                "condition": "Lightly Played",
                "graded": False,
            },
        ],
    )
    monkeypatch.setattr(
        "pkmnprices_client.cardmarket_offers_for_tcgplayer_id",
        lambda *_a, **_k: [
            {
                "price": 95.0,
                "currency": "EUR",
                "condition": "Near Mint",
                "seller": "EUSeller",
                "seller_country": "DE",
            }
        ],
    )
    monkeypatch.setattr(
        "pkmnprices_client.population_for_tcgplayer_id",
        lambda *_a, **_k: {
            "source": "pkmnprices",
            "variant": "Holofoil",
            "total_population": 1000,
            "total_gems": 50,
            "gem_rate": 5.0,
            "grade_rows": [
                {"grade": "10", "count": 40, "share_pct": 4.0, "percent_higher": 0.5}
            ],
        },
    )
    out = build_market_comps("skyridge-h30", limit=8)
    assert out["ebay_sold_stats"]["n"] == 2
    assert out["ebay_sold_stats"]["median"] == 110.0
    assert out["cardmarket_stats"]["lowest"] == 95.0
    assert out["population"]["total_population"] == 1000
    assert out["population"]["grade_rows"][0]["grade"] == "10"

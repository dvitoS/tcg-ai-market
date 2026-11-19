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


def test_nm_history_prefers_holofoil_when_collapsing(monkeypatch) -> None:
    monkeypatch.setattr(client, "pkmn_api_key", lambda: "pk-test")
    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", lambda _tcp: 7)

    def _fake_get(path, params=None):
        assert "variant" not in (params or {})
        return {
            "data": [
                {
                    "date": "2024-04-01",
                    "avg": 5.0,
                    "condition": "Near Mint",
                    "source": "tcgplayer",
                    "variant": "Normal",
                },
                {
                    "date": "2024-04-01",
                    "avg": 12.0,
                    "condition": "Near Mint",
                    "source": "tcgplayer",
                    "variant": "Holofoil",
                },
            ]
        }

    monkeypatch.setattr(client, "_get", _fake_get)
    rows = client.nm_history_for_tcgplayer_id("555")
    assert rows == [{"date": "2024-04-01", "price": 12.0}]


def test_nm_history_condition_lp(monkeypatch) -> None:
    monkeypatch.setattr(client, "pkmn_api_key", lambda: "pk-test")
    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", lambda _tcp: 7)

    def _fake_get(path, params=None):
        assert params["condition"] == "Lightly Played"
        return {
            "data": [
                {
                    "date": "2024-04-03",
                    "avg": 4.25,
                    "condition": "Lightly Played",
                    "source": "tcgplayer",
                    "variant": "Holofoil",
                }
            ]
        }

    monkeypatch.setattr(client, "_get", _fake_get)
    rows = client.nm_history_for_tcgplayer_id("555", condition="LP")
    assert rows == [{"date": "2024-04-03", "price": 4.25}]


def test_soft_ink_condition_to_pkmn_eur() -> None:
    assert client.soft_ink_condition_to_pkmn("LP", currency="eur") == "Light Played"
    assert client.soft_ink_condition_to_pkmn("MP", currency="usd") == "Moderately Played"


def test_nm_history_filters_variant(monkeypatch) -> None:
    monkeypatch.setattr(client, "pkmn_api_key", lambda: "pk-test")
    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", lambda _tcp: 7)

    def _fake_get(path, params=None):
        assert params["variant"] == "Reverse Holofoil"
        return {
            "data": [
                {
                    "date": "2024-04-02",
                    "avg": 7.5,
                    "condition": "Near Mint",
                    "source": "tcgplayer",
                    "variant": "Reverse Holofoil",
                }
            ]
        }

    monkeypatch.setattr(client, "_get", _fake_get)
    rows = client.nm_history_for_tcgplayer_id("555", variant="Reverse")
    assert rows == [{"date": "2024-04-02", "price": 7.5}]


def test_nm_history_cardmarket_eur(monkeypatch) -> None:
    monkeypatch.setattr(client, "pkmn_api_key", lambda: "pk-test")
    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", lambda _tcp: 7)

    def _fake_get(path, params=None):
        assert path == "/v1/cards/7/prices/history"
        assert params["currency"] == "eur"
        assert params["condition"] == "Near Mint"
        return {
            "data": [
                {
                    "date": "2024-03-02",
                    "avg": 9.5,
                    "condition": "Near Mint",
                    "source": "cardmarket",
                    "currency": "EUR",
                },
                {
                    "date": "2024-03-01",
                    "avg": 8.0,
                    "condition": "Near Mint",
                    "source": "cardmarket",
                    "currency": "EUR",
                },
                {
                    "date": "2024-03-01",
                    "avg": 99.0,
                    "condition": "Near Mint",
                    "source": "tcgplayer",
                    "currency": "USD",
                },
            ]
        }

    monkeypatch.setattr(client, "_get", _fake_get)
    rows = client.nm_history_for_tcgplayer_id("555", currency="eur")
    assert rows == [
        {"date": "2024-03-01", "price": 8.0},
        {"date": "2024-03-02", "price": 9.5},
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


def test_variant_spot_for_condition_printing(monkeypatch) -> None:
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
                    "market_price": 20.0,
                    "source": "tcgplayer",
                },
                {
                    "currency": "USD",
                    "condition": "Lightly Played",
                    "variant": "Reverse Holofoil",
                    "market_price": 11.5,
                    "source": "tcgplayer",
                },
            ]
        },
    )
    hit = client.variant_spot_for_tcgplayer_id(
        "999", condition="LP", printing="Reverse"
    )
    assert hit is not None
    assert hit["price"] == 11.5
    assert hit["variant"] == "Reverse Holofoil"
    assert hit["pkmn_card_id"] == 3


def test_batch_variant_spots_one_get_per_tcp(monkeypatch) -> None:
    monkeypatch.setattr(client, "pkmnprices_configured", lambda: True)
    gets: list[int] = []

    def _find(tcp):
        return 7 if str(tcp) == "100" else None

    def _get_card(pid, currency="usd"):
        gets.append(int(pid))
        return {
            "prices": [
                {
                    "currency": "USD",
                    "condition": "Lightly Played",
                    "variant": "Normal",
                    "market_price": 6.0,
                    "source": "tcgplayer",
                },
                {
                    "currency": "USD",
                    "condition": "Moderately Played",
                    "variant": "Holofoil",
                    "market_price": 4.0,
                    "source": "tcgplayer",
                },
            ]
        }

    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", _find)
    monkeypatch.setattr(client, "get_card", _get_card)
    out = client.batch_variant_spots(
        [
            {"tcgplayerId": "100", "condition": "LP", "printing": "Normal"},
            {"tcgplayerId": "100", "condition": "MP", "printing": "Holo"},
            {"tcgplayerId": "999", "condition": "LP", "printing": "Normal"},
        ]
    )
    assert gets == [7]
    assert out["100|LP|Normal"]["price"] == 6.0
    assert out["100|MP|Holo"]["price"] == 4.0
    assert "999|LP|Normal" not in out


def test_population_for_tcgplayer_id(monkeypatch) -> None:
    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", lambda _tcp: 18176)

    def _fake_get(path, params=None):
        assert path == "/v1/cards/18176/population"
        return {
            "card_id": 18176,
            "variants": [
                {
                    "variant": "Normal",
                    "total_population": 100,
                    "total_gems": 10,
                    "gem_rate": 10.0,
                    "grades": {"9": 40, "10": 10},
                    "percent_higher": {"9": 20.0},
                    "graders": {
                        "PSA": {
                            "total": 80,
                            "gems": 8,
                            "gem_rate": 10.0,
                            "grades": {"9": 30, "10": 8},
                            "pop_report_url": "https://example.com/pop",
                        }
                    },
                },
                {
                    "variant": "Holofoil",
                    "total_population": 200,
                    "total_gems": 40,
                    "gem_rate": 20.0,
                    "grades": {"9": 80, "10": 40},
                    "percent_higher": {"9": 25.0},
                    "graders": {
                        "PSA": {
                            "total": 150,
                            "gems": 30,
                            "gem_rate": 20.0,
                            "grades": {"9": 60, "10": 30},
                            "pop_report_url": "https://example.com/holo",
                        }
                    },
                },
            ],
        }

    monkeypatch.setattr(client, "_get", _fake_get)
    hit = client.population_for_tcgplayer_id("555")
    assert hit is not None
    assert hit["variant"] == "Holofoil"
    assert hit["psa_10"] == 30
    assert hit["gem_rate_for_ev"] == 20.0
    assert hit["pkmn_card_id"] == 18176


def test_psa_series_from_comps_median() -> None:
    points = client.psa_series_from_comps(
        [
            {"date": "2024-05-01", "price": 100.0},
            {"date": "2024-05-01", "price": 120.0},
            {"date": "2024-05-01", "price": 140.0},
            {"date": "2024-05-02", "price": 130.0},
        ]
    )
    assert points == [
        {"date": "2024-05-01", "price": 120.0},
        {"date": "2024-05-02", "price": 130.0},
    ]


def test_psa_history_for_tcgplayer_id(monkeypatch) -> None:
    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", lambda _tcp: 42)

    def _fake_get(path, params=None):
        assert path == "/v1/cards/42/listings/ebay"
        assert params["grader"] == "PSA"
        assert params["grade"] == "10"
        return {
            "data": [
                {
                    "grader": "PSA",
                    "grade": "10",
                    "currency": "USD",
                    "price": 50.0,
                    "sold_at": "2024-06-01",
                    "title": "PSA 10 Foo",
                },
                {
                    "grader": "PSA",
                    "grade": "10",
                    "currency": "USD",
                    "price": 55.0,
                    "sold_at": "2024-06-02T12:00:00Z",
                    "title": "PSA 10 Foo",
                },
                {
                    "grader": "CGC",
                    "grade": "10",
                    "currency": "USD",
                    "price": 99.0,
                    "sold_at": "2024-06-03",
                },
            ]
        }

    monkeypatch.setattr(client, "_get", _fake_get)
    points, stats = client.psa_history_for_tcgplayer_id("777", grade=10)
    assert points == [
        {"date": "2024-06-01", "price": 50.0},
        {"date": "2024-06-02", "price": 55.0},
    ]
    assert stats["sales_count"] == 2
    assert stats["price"] == 55.0
    assert stats["canonical"] == "PSA 10"
    assert stats["price_status"] == "ebay_comps"


def test_sealed_quote_for_tcgplayer_id(monkeypatch) -> None:
    monkeypatch.setattr(client, "find_sealed_id_by_tcgplayer_id", lambda _tcp: 99)
    monkeypatch.setattr(
        client,
        "get_sealed",
        lambda _id, currency="usd": {
            "id": 99,
            "tcg_player_id": 624679,
            "name": "Destined Rivals Booster Box",
            "image_url": "https://example.com/box.jpg",
            "set": {"id": 1, "name": "Destined Rivals"},
            "prices": [
                {
                    "source": "tcgplayer",
                    "currency": "USD",
                    "market_price": 199.5,
                }
            ],
        },
    )
    hit = client.sealed_quote_for_tcgplayer_id("624679")
    assert hit is not None
    assert hit["card_id"] == "sealed:624679"
    assert hit["spot_usd"] == 199.5
    assert hit["source"] == "pkmnprices"
    assert hit["set_name"] == "Destined Rivals"


def test_search_sealed_by_name(monkeypatch) -> None:
    calls = {"list": 0, "get": 0}

    def _fake_get(path, params=None):
        if path == "/v1/sealed":
            calls["list"] += 1
            assert params["name"] == "etb"
            return {
                "data": [
                    {
                        "id": 11,
                        "tcg_player_id": 624676,
                        "name": "Destined Rivals ETB",
                        "image_url": "https://example.com/etb.jpg",
                        "set": {"id": 1, "name": "Destined Rivals"},
                    }
                ]
            }
        if path == "/v1/sealed/11":
            calls["get"] += 1
            return {
                "id": 11,
                "tcg_player_id": 624676,
                "name": "Destined Rivals Elite Trainer Box",
                "image_url": "https://example.com/etb.jpg",
                "set": {"id": 1, "name": "Destined Rivals"},
                "prices": [
                    {"source": "tcgplayer", "currency": "USD", "market_price": 106.0}
                ],
            }
        raise AssertionError(path)

    monkeypatch.setattr(client, "_get", _fake_get)
    hits = client.search_sealed_by_name("etb", limit=4)
    assert calls == {"list": 1, "get": 1}
    assert len(hits) == 1
    assert hits[0]["tcgplayer_id"] == "624676"
    assert hits[0]["spot_usd"] == 106.0
    assert hits[0]["source"] == "pkmnprices"


def test_ebay_sold_search_url_prefers_completed_search() -> None:
    url = client.ebay_sold_search_url(
        title="Mega Rayquaza ex Delta Reign",
        listing_url="https://www.ebay.com/itm/123456789012",
    )
    assert url is not None
    assert "LH_Sold=1" in url
    assert "LH_Complete=1" in url
    assert "Mega+Rayquaza" in url or "Mega%20Rayquaza" in url
    assert "/itm/" not in url


def test_tcgplayer_offers_for_tcgplayer_id(monkeypatch) -> None:
    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", lambda _tcp: 42)
    calls: list[dict] = []

    def _fake_get(path, params=None):
        assert path == "/v1/cards/42/listings/tcgplayer"
        calls.append(dict(params or {}))
        assert params["sort"] == "total_asc"
        return {
            "data": [
                {
                    "printing": "Holofoil",
                    "condition": "Near Mint",
                    "language": "English",
                    "price": 50.0,
                    "shipping_price": 0.99,
                    "seller_name": "ShopA",
                    "quantity": 2,
                },
                {
                    "printing": "Normal",
                    "condition": "Near Mint",
                    "price": 0,
                    "shipping_price": 0,
                    "seller_name": "Skip",
                },
            ]
        }

    monkeypatch.setattr(client, "_get", _fake_get)
    rows = client.tcgplayer_offers_for_tcgplayer_id("888001", limit=8)
    assert len(rows) == 1
    assert rows[0]["price"] == 50.0
    assert rows[0]["shipping_price"] == 0.99
    assert rows[0]["seller"] == "ShopA"
    assert rows[0]["url"] == "https://www.tcgplayer.com/product/888001"
    assert calls[0]["condition"] == "Near Mint"


def test_tcgplayer_offers_missing_pkmn_id_raises(monkeypatch) -> None:
    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", lambda _tcp: None)
    try:
        client.tcgplayer_offers_for_tcgplayer_id("888001")
        assert False, "expected PkmnPricesError"
    except client.PkmnPricesError as exc:
        assert "no card" in str(exc).lower()


def test_tcgplayer_offers_403_raises(monkeypatch) -> None:
    import requests

    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", lambda _tcp: 42)

    def _fake_get(_path, params=None):
        res = requests.Response()
        res.status_code = 403
        raise client.PkmnPricesError(
            "PkmnPrices forbidden — plan may lack this endpoint",
            response=res,
        )

    monkeypatch.setattr(client, "_get", _fake_get)
    try:
        client.tcgplayer_offers_for_tcgplayer_id("888001")
        assert False, "expected PkmnPricesError"
    except client.PkmnPricesError as exc:
        assert getattr(exc.response, "status_code", None) == 403


def test_tcgplayer_offers_broadens_when_nm_filter_empty(monkeypatch) -> None:
    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", lambda _tcp: 42)
    calls: list[dict] = []

    def _fake_get(_path, params=None):
        p = dict(params or {})
        calls.append(p)
        if p.get("condition") == "Near Mint":
            return {"data": []}
        return {
            "data": [
                {
                    "printing": "Holofoil",
                    "condition": "Near Mint",
                    "price": 44.0,
                    "shipping_price": 0,
                    "seller_name": "Desk",
                },
                {
                    "printing": "Holofoil",
                    "condition": "Lightly Played",
                    "price": 30.0,
                    "shipping_price": 0,
                    "seller_name": "LP",
                },
            ]
        }

    monkeypatch.setattr(client, "_get", _fake_get)
    rows = client.tcgplayer_offers_for_tcgplayer_id("888001", limit=8)
    assert len(rows) == 1
    assert rows[0]["price"] == 44.0
    assert any("condition" not in c for c in calls)


def test_ebay_sold_listings_drops_shared_and_rewrites_url(monkeypatch) -> None:
    monkeypatch.setattr(client, "find_card_id_by_tcgplayer_id", lambda _tcp: 42)

    def _fake_get(path, params=None):
        assert path == "/v1/cards/42/listings/ebay"
        assert params["graded"] == "false"
        return {
            "data": [
                {
                    "title": "Exact Match Card",
                    "price": 100.0,
                    "currency": "USD",
                    "sold_at": "2026-11-01",
                    "listing_url": "https://www.ebay.com/itm/111222333444",
                    "attribution": "exact",
                    "condition": "Near Mint",
                },
                {
                    "title": "Shared Sibling Printing",
                    "price": 999.0,
                    "currency": "USD",
                    "sold_at": "2026-11-02",
                    "listing_url": "https://www.ebay.com/itm/999888777666",
                    "attribution": "shared",
                },
                {
                    "title": "No sale date",
                    "price": 50.0,
                    "currency": "USD",
                    "listing_url": "https://www.ebay.com/itm/555",
                    "attribution": "exact",
                },
            ]
        }

    monkeypatch.setattr(client, "_get", _fake_get)
    rows = client.ebay_sold_listings_for_tcgplayer_id("777", limit=10)
    assert len(rows) == 1
    assert rows[0]["price"] == 100.0
    assert rows[0]["title"] == "Exact Match Card"
    assert rows[0]["url"] and "LH_Sold=1" in rows[0]["url"]
    assert "/itm/" not in (rows[0]["url"] or "")

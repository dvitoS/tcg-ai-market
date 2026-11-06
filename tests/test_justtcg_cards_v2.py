"""Unit tests for JustTCG /v2/cards NM request shaping (no live API)."""

from __future__ import annotations

import justtcg_client as jt


def test_v2_raw_params_exclude_graded_and_include_history() -> None:
    params = jt._v2_raw_params(tcgplayer_id="123")
    assert params["regions"] == "NA"
    assert params["graded"] == "exclude"
    assert params["include"] == jt._v2_history_include()
    assert params["tcgplayer_id"] == "123"
    assert f"price_history.{jt.JUSTTCG_HISTORY_DURATION}" in params["include"]


def test_v2_spot_params_skip_price_history() -> None:
    params = jt._v2_spot_params()
    assert params["graded"] == "exclude"
    assert params["include"] == "periods.30d"
    assert "price_history" not in params["include"]


def test_v2_batch_path_history_vs_spot() -> None:
    hist = jt._v2_batch_path(history=True)
    spot = jt._v2_batch_path(history=False)
    assert hist.startswith("/cards?")
    assert "graded=exclude" in hist
    assert "regions=NA" in hist
    assert f"price_history.{jt.JUSTTCG_HISTORY_DURATION}" in hist
    assert "price_history" not in spot
    assert "periods.30d" in spot


def test_parse_next_cursor_from_link() -> None:
    link = (
        '<https://api.justtcg.com/v2/cards?game=pokemon&cursor=eyJvIjoyMH0>; '
        'rel="next"'
    )
    assert jt._parse_next_cursor(link) == "eyJvIjoyMH0"
    assert jt._parse_next_cursor(None) is None


def test_variant_price_reads_na_market() -> None:
    assert (
        jt.variant_price_usd(
            {
                "markets": [
                    {
                        "region": "NA",
                        "price": 9.5,
                        "price_status": "current",
                        "last_price": None,
                    }
                ]
            }
        )
        == 9.5
    )
    assert (
        jt.variant_price_usd(
            {
                "markets": [
                    {
                        "region": "NA",
                        "price": None,
                        "price_status": "expired",
                        "last_price": 12.5,
                    }
                ]
            }
        )
        == 12.5
    )
    assert (
        jt.variant_price_usd(
            {
                "markets": [
                    {
                        "region": "NA",
                        "price": None,
                        "price_status": "unpriced",
                        "last_price": None,
                    }
                ]
            }
        )
        is None
    )


def test_variant_price_respects_v1_expired_status() -> None:
    assert (
        jt.variant_price_usd(
            {
                "price": None,
                "priceStatus": "expired",
                "lastKnownPrice": 12.5,
            }
        )
        == 12.5
    )
    assert (
        jt.variant_price_usd(
            {
                "price": None,
                "priceStatus": "unpriced",
                "lastKnownPrice": None,
            }
        )
        is None
    )


def test_pick_nm_skips_graded_variants() -> None:
    picked = jt.pick_nm_variant(
        [
            {
                "type": "graded",
                "grading": {"company": "PSA", "grade": 10},
                "markets": [{"region": "NA", "price": 999.0, "price_status": "current"}],
            },
            {
                "type": "raw",
                "condition": "Near Mint",
                "printing": "Holofoil",
                "markets": [{"region": "NA", "price": 15.0, "price_status": "current"}],
            },
        ]
    )
    assert picked is not None
    assert picked.get("type") == "raw"
    assert jt.variant_price_usd(picked) == 15.0


def test_card_tcgplayer_id_from_external_ids() -> None:
    assert (
        jt.card_tcgplayer_id(
            {"external_ids": {"tcgplayer": "42445"}, "tcgplayerId": None}
        )
        == "42445"
    )
    assert jt.card_tcgplayer_id({"tcgplayer_id": "99"}) == "99"
    assert jt.card_tcgplayer_id({"tcgplayerId": "88"}) == "88"


def test_history_points_from_v2_markets() -> None:
    points = jt.history_points_from_variant(
        {
            "markets": [
                {
                    "region": "NA",
                    "price": 10.0,
                    "price_status": "current",
                    "price_history": [
                        {"t": 1_704_067_200, "p": 9.0},
                        {"t": 1_704_153_600, "p": 9.5},
                    ],
                }
            ]
        }
    )
    assert len(points) >= 2
    assert points[0]["price"] == 9.0
    assert points[1]["price"] == 9.5


def test_search_uses_v2_query(monkeypatch) -> None:
    seen: dict = {}

    def fake_get_v2(path, params=None, **_k):
        seen["path"] = path
        seen["params"] = dict(params or {})
        return {"data": []}

    monkeypatch.setattr(jt, "_get_v2", fake_get_v2)
    jt._search_cards_raw("Pikachu 25", limit=20, number="025")
    assert seen["path"] == "/cards"
    assert seen["params"]["game"] == "pokemon"
    assert seen["params"]["query"] == "Pikachu 25"
    assert seen["params"]["number"] == "25"
    assert seen["params"]["graded"] == "exclude"
    assert seen["params"]["regions"] == "NA"
    assert "q" not in seen["params"]
    assert "include_price_history" not in seen["params"]


def test_fetch_card_uses_v2_tcgplayer_id(monkeypatch) -> None:
    seen: dict = {}
    calls = {"get_v2": 0, "post_v2": 0}

    def fake_get_v2(path, params=None, **_k):
        calls["get_v2"] += 1
        seen["params"] = dict(params or {})
        return {"data": []}

    def fake_post_v2(path, body):
        calls["post_v2"] += 1
        return {"data": [{"tcgplayer_id": "1"}]}

    monkeypatch.setattr(jt, "_get_v2", fake_get_v2)
    monkeypatch.setattr(jt, "_post_v2", fake_post_v2)
    assert jt.fetch_card_by_tcgplayer_id("999") is None
    assert calls == {"get_v2": 1, "post_v2": 0}
    assert seen["params"]["tcgplayer_id"] == "999"
    assert seen["params"]["graded"] == "exclude"


def test_batch_variant_lookups_snake_case_spot(monkeypatch) -> None:
    seen: dict = {}

    def fake_post_v2(path, body):
        seen["path"] = path
        seen["body"] = body
        return {"data": []}

    monkeypatch.setattr(jt, "_post_v2", fake_post_v2)
    jt.batch_variant_lookups(
        [{"tcgplayerId": "42", "condition": "LP", "printing": "Reverse"}]
    )
    assert "graded=exclude" in seen["path"]
    assert "periods.30d" in seen["path"]
    assert "price_history" not in seen["path"]
    assert seen["body"][0]["tcgplayer_id"] == "42"
    assert seen["body"][0]["condition"] == "LP"
    assert seen["body"][0]["printing"] == "Reverse Holofoil"
    assert "tcgplayerId" not in seen["body"][0]


def test_batch_by_tcgplayer_ids_snake_case_history(monkeypatch) -> None:
    seen: dict = {}

    def fake_post_v2(path, body):
        seen["path"] = path
        seen["body"] = body
        return {"data": []}

    monkeypatch.setattr(jt, "_post_v2", fake_post_v2)
    jt.batch_by_tcgplayer_ids(["101", "102"])
    assert seen["body"] == [
        {"tcgplayer_id": "101", "condition": "NM"},
        {"tcgplayer_id": "102", "condition": "NM"},
    ]
    assert f"price_history.{jt.JUSTTCG_HISTORY_DURATION}" in seen["path"]


def test_fetch_set_cards_page_uses_cursor(monkeypatch) -> None:
    seen: list[dict] = []

    def fake_page(path, params=None):
        seen.append(dict(params or {}))
        if "cursor" not in (params or {}):
            return {"data": [{"id": "a"}]}, "cur-2"
        return {"data": [{"id": "b"}]}, None

    monkeypatch.setattr(jt, "_get_v2_page", fake_page)
    rows, nxt = jt.fetch_set_cards_page("base-set-pokemon", limit=20)
    assert [r["id"] for r in rows] == ["a"]
    assert nxt == "cur-2"
    rows2, nxt2 = jt.fetch_set_cards_page(
        "base-set-pokemon", cursor="cur-2", limit=20
    )
    assert [r["id"] for r in rows2] == ["b"]
    assert nxt2 is None
    assert "offset" not in seen[0]
    assert seen[0]["set"] == "base-set-pokemon"
    assert seen[0]["graded"] == "exclude"
    assert seen[1]["cursor"] == "cur-2"

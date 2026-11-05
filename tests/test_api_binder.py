"""Binder / set-completion API (demo board + demo portfolio)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.deps import _dev_user
from api.main import app
from api.portfolio_service import add_lot, list_portfolio


def setup_function() -> None:
    clear_board_cache()


def test_binder_sets_lists_completion() -> None:
    client = TestClient(app)
    res = client.get("/api/binder/sets")
    assert res.status_code == 200
    body = res.json()
    assert "sets" in body
    assert body["demo"] is True
    if body["source"] == "empty":
        return
    assert len(body["sets"]) >= 1
    row = body["sets"][0]
    assert row["total"] >= 1
    assert 0 <= float(row["pct"]) <= 100
    assert row["owned"] + row["missing"] == row["total"]
    assert float(row["missing_cost"]) >= 0


def test_binder_set_detail_matches_owned_lots() -> None:
    client = TestClient(app)
    catalog = client.get("/api/catalog", params={"limit": 1})
    assert catalog.status_code == 200
    items = catalog.json()["items"]
    if not items:
        return
    card = items[0]
    set_name = card.get("set_name")
    if not set_name:
        return

    user_id = str(_dev_user()["id"])
    # Ensure at least one owned card in that set (demo seed may already own some).
    lots = list_portfolio(user_id=user_id, include_sold=False)
    owned_ids = {str(l.get("card_id")) for l in lots}
    if card["id"] not in owned_ids:
        add_lot(
            user_id=user_id,
            card_id=card["id"],
            quantity=1,
            purchase_price=float(card.get("price") or 1.0),
        )

    res = client.get("/api/binder", params={"set_name": set_name, "missing_limit": 50})
    assert res.status_code == 200
    body = res.json()
    assert body["set_name"] == set_name
    assert body["total"] >= 1
    assert body["owned"] + body["missing"] == body["total"]
    assert card["id"] in body["owned_ids"]
    missing_ids = {m["id"] for m in body["missing_cards"]}
    assert card["id"] not in missing_ids
    for row in body["missing_cards"]:
        assert row["id"]
        assert row["name"]


def test_binder_unknown_set_404() -> None:
    client = TestClient(app)
    res = client.get("/api/binder", params={"set_name": "__no_such_set__"})
    assert res.status_code == 404

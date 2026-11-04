"""Portfolio lot edit / sell API (demo mode)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app


def setup_function() -> None:
    clear_board_cache()


def test_update_and_sell_lot_roundtrip() -> None:
    client = TestClient(app)
    catalog = client.get("/api/catalog", params={"limit": 1})
    assert catalog.status_code == 200
    items = catalog.json()["items"]
    if not items:
        return
    card_id = items[0]["id"]

    created = client.post(
        "/api/portfolio/lots",
        json={"card_id": card_id, "quantity": 2, "purchase_price": 3.5, "condition": "NM"},
    )
    assert created.status_code == 201
    lot_id = created.json()["id"]

    updated = client.patch(
        f"/api/portfolio/lots/{lot_id}",
        json={"quantity": 3, "purchase_price": 4.25, "condition": "LP"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["quantity"] == 3
    assert float(body["purchase_price"]) == 4.25
    assert body["condition"] == "LP"
    assert str(body.get("status") or "open").lower() != "sold"

    sold = client.post(
        f"/api/portfolio/lots/{lot_id}/sell",
        json={"sale_price": 5.5},
    )
    assert sold.status_code == 200
    sold_body = sold.json()
    assert str(sold_body.get("status") or "").lower() == "sold"
    assert float(sold_body["sale_price"]) == 5.5
    assert sold_body.get("sale_date")

    book = client.get("/api/portfolio", params={"include_sold": True})
    assert book.status_code == 200
    rows = book.json()["items"]
    hit = next((row for row in rows if str(row["id"]) == str(lot_id)), None)
    assert hit is not None
    assert str(hit.get("status") or "").lower() == "sold"


def test_sell_rejects_non_positive_price() -> None:
    client = TestClient(app)
    portfolio = client.get("/api/portfolio")
    assert portfolio.status_code == 200
    open_lots = [
        row
        for row in portfolio.json()["items"]
        if str(row.get("status") or "open").lower() != "sold"
    ]
    if not open_lots:
        return
    lot_id = open_lots[0]["id"]
    bad = client.post(f"/api/portfolio/lots/{lot_id}/sell", json={"sale_price": 0})
    assert bad.status_code == 400

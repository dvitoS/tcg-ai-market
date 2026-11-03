"""Scanner + dealer desk API smoke tests (demo board)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app


def setup_function() -> None:
    clear_board_cache()


def test_scanner_returns_opportunities_or_empty() -> None:
    client = TestClient(app)
    res = client.get("/api/scanner", params={"min_growth": 0, "limit": 12})
    assert res.status_code == 200
    body = res.json()
    assert "opportunities" in body
    assert "warnings" in body
    assert body["scoped"] >= 0
    if body["source"] != "empty":
        assert body["scoped"] > 0


def test_dealer_status_and_score_sample_csv() -> None:
    client = TestClient(app)
    status = client.get("/api/dealer/status")
    assert status.status_code == 200
    st = status.json()
    assert st["allowed"] is True
    sample = st["sample_csv"]

    scored = client.post(
        "/api/dealer/score",
        json={"csv_text": sample, "fee_pct": 13, "ship_usd": 4},
    )
    assert scored.status_code == 200
    body = scored.json()
    assert body["rows"] >= 1
    assert "items" in body
    assert body["matched"] >= 1

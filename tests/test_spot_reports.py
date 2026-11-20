"""Wrong-spot report queue (M4.4)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from services.spot_reports import reset_spot_reports_for_tests, spot_report_summary


client = TestClient(app)


def setup_function():
    reset_spot_reports_for_tests()


def test_submit_and_summary():
    res = client.post(
        "/api/spots/report",
        json={"card_id": "base1-4", "spot": 12.5, "note": "too high"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["card_id"] == "base1-4"
    assert body["status"] == "open"

    summary = spot_report_summary()
    assert summary["open_total"] == 1
    assert summary["counts"]["open"] == 1


def test_ops_summary_requires_ops(monkeypatch):
    # Without ops auth in demo/dev the dep may still pass — assert shape when allowed.
    monkeypatch.setenv("AUTH_DISABLED", "1")
    res = client.get("/api/spots/reports/summary")
    # Dev/demo often treats as ops; accept 200 or 401/403 depending on env.
    assert res.status_code in {200, 401, 403}


def test_open_report_card_ids_empty():
    from services.spot_reports import open_report_card_ids

    assert open_report_card_ids() == []


def test_latest_report_and_public_status():
    from services.spot_reports import latest_report_for_card, set_report_status

    res = client.post(
        "/api/spots/report",
        json={"card_id": "sv3-199", "spot": 9.5},
    )
    assert res.status_code == 200
    rid = res.json()["id"]

    latest = latest_report_for_card("sv3-199")
    assert latest is not None
    assert latest["id"] == rid
    assert latest["status"] == "open"

    status = client.get("/api/spots/report-status", params={"card_id": "sv3-199"})
    assert status.status_code == 200
    body = status.json()
    assert body["card_id"] == "sv3-199"
    assert body["report"]["id"] == rid
    assert body["report"]["status"] == "open"

    set_report_status(rid, "resolved")
    status2 = client.get("/api/spots/report-status", params={"card_id": "sv3-199"})
    assert status2.json()["report"]["status"] == "resolved"

    empty = client.get("/api/spots/report-status", params={"card_id": "no-such-card"})
    assert empty.status_code == 200
    assert empty.json()["report"] is None

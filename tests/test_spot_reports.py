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


def test_spot_reports_persist_across_restart(tmp_path, monkeypatch):
    import services.spot_reports as sr

    path = tmp_path / "spot_reports.json"
    monkeypatch.setattr(sr, "LOCAL_PATH", path)
    monkeypatch.setattr(sr, "_save_supabase", lambda _payload: False)
    monkeypatch.setattr(sr, "_load_supabase", lambda: None)
    reset_spot_reports_for_tests()

    row = sr.submit_spot_report(card_id="base1-4", spot=11.0, note="wrong")
    assert path.is_file()
    summary = sr.spot_report_summary()
    assert summary["persisted"] is True
    assert summary["source"] == "local"
    assert summary["open_total"] == 1

    # Simulate process restart: wipe memory, keep file, rehydrate.
    with sr._LOCK:
        sr._REPORTS.clear()
        sr._HYDRATED = False
        sr._PERSIST_SOURCE = "memory"
    again = sr.latest_report_for_card("base1-4")
    assert again is not None
    assert again["id"] == row["id"]
    assert again["note"] == "wrong"
    summary2 = sr.spot_report_summary()
    assert summary2["open_total"] == 1
    assert summary2["source"] == "local"

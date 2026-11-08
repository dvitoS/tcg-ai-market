"""Soft-launch funnel ingest."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from services.funnel import record_events, reset_funnel_for_tests


client = TestClient(app)


def setup_function():
    reset_funnel_for_tests()


def test_record_events_allowlist():
    out = record_events(
        [
            {"event": "landing_view", "session": "s1"},
            {"event": "not_a_real_event", "session": "s1"},
            {"event": "pro_checkout_click", "session": "s1", "props": {"ok": True}},
        ]
    )
    assert out == {"accepted": 2, "rejected": 1}


def test_funnel_api_batch_and_summary():
    res = client.post(
        "/api/funnel/events",
        json={
            "events": [
                {"event": "landing_view", "session": "abc"},
                {"event": "dotd_cta", "session": "abc", "props": {"target": "/pro"}},
                {"event": "share_copy", "session": "abc", "props": {"surface": "trade"}},
                {"event": "spam_event"},
            ]
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] == 3
    assert body["rejected"] == 1

    summary = client.get("/api/funnel/summary")
    assert summary.status_code == 200
    data = summary.json()
    assert data["counts"]["landing_view"] == 1
    assert data["counts"]["dotd_cta"] == 1
    assert data["counts"]["share_copy"] == 1
    assert data["total"] == 3
    assert "share_png" in data["allowed_events"]
    assert "landing_view" in data["allowed_events"]

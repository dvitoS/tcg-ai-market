"""Watchlist digest formatting + alert collection without Streamlit dismiss state."""

from __future__ import annotations

import pandas as pd

from services.alerts import WatchAlert, collect_watchlist_alerts
from services.email_alerts import format_digest, smtp_configured


def test_format_digest_includes_card():
    body = format_digest(
        [
            WatchAlert(
                card_id="sv3-1",
                name="Pikachu",
                expected_pct=12.5,
                signal="BUY",
                price=1.25,
                reason="ai",
            )
        ],
        threshold_pct=5.0,
    )
    assert "Pikachu" in body
    assert "sv3-1" in body
    assert "12.5" in body


def test_collect_alerts_respects_threshold_and_dismissed():
    market = pd.DataFrame(
        [
            {
                "id": "a",
                "name": "A",
                "expected_change_pct": 10.0,
                "price_change_7d_pct": 1.0,
                "signal": "BUY",
                "price": 2.0,
                "confidence_ok": True,
            },
            {
                "id": "b",
                "name": "B",
                "expected_change_pct": 1.0,
                "price_change_7d_pct": 0.5,
                "signal": "HOLD",
                "price": 3.0,
                "confidence_ok": True,
            },
        ]
    )
    watch = pd.DataFrame(
        [
            {"card_id": "a", "name": "A"},
            {"card_id": "b", "name": "B"},
        ]
    )
    alerts = collect_watchlist_alerts(
        market, watch, threshold_pct=5.0, dismissed=set()
    )
    assert [a.card_id for a in alerts] == ["a"]
    assert alerts[0].reason == "ai"

    alerts2 = collect_watchlist_alerts(
        market, watch, threshold_pct=5.0, dismissed={"a"}
    )
    assert alerts2 == []


def test_collect_alerts_fires_on_price_move():
    market = pd.DataFrame(
        [
            {
                "id": "c",
                "name": "C",
                "expected_change_pct": 0.5,
                "price_change_7d_pct": -8.0,
                "signal": "HOLD",
                "price": 4.0,
                "confidence_ok": True,
            }
        ]
    )
    watch = pd.DataFrame([{"card_id": "c", "name": "C"}])
    alerts = collect_watchlist_alerts(
        market, watch, threshold_pct=5.0, dismissed=set()
    )
    assert len(alerts) == 1
    assert alerts[0].reason == "price"
    assert alerts[0].price_change_pct == -8.0
    body = format_digest(alerts, threshold_pct=5.0)
    assert "7d price" in body


def test_smtp_configured_false_without_secrets(monkeypatch):
    import services.email_alerts as email_alerts

    monkeypatch.setattr(email_alerts, "_clean", lambda name: "")
    assert smtp_configured() is False

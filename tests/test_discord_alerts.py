"""Discord sure-only digest payload + config helpers."""

from __future__ import annotations

import pandas as pd

from services.alerts import WatchAlert
from services.discord_alerts import (
    build_discord_payload,
    collect_aggregated_sure_alerts,
    discord_configured,
)
from trading_signals import SIGNAL_BUY, SIGNAL_HOLD


def test_discord_configured_requires_webhook_host(monkeypatch):
    import services.discord_alerts as discord_alerts

    monkeypatch.setattr(discord_alerts, "_clean", lambda name: "")
    assert discord_configured() is False
    monkeypatch.setattr(
        discord_alerts,
        "_clean",
        lambda name: "https://discord.com/api/webhooks/1/abc"
        if name == "DISCORD_WEBHOOK_URL"
        else "",
    )
    assert discord_configured() is True


def test_build_discord_payload_embeds_cards():
    alerts = [
        WatchAlert(
            card_id="sv3-1",
            name="Pikachu",
            expected_pct=11.0,
            signal=SIGNAL_BUY,
            price=2.5,
            reason="ai",
            sure=True,
        )
    ]
    payload = build_discord_payload(alerts, threshold_pct=5.0, sure_only=True)
    assert "sure-only" in payload["content"].lower()
    assert payload["embeds"]
    assert "Pikachu" in payload["embeds"][0]["fields"][0]["name"]
    assert "sv3-1" in payload["embeds"][0]["fields"][0]["value"]


def test_collect_aggregated_dedupes_by_card(monkeypatch):
    import services.discord_alerts as discord_alerts

    market = pd.DataFrame(
        [
            {
                "id": "a",
                "name": "A",
                "expected_change_pct": 10.0,
                "price_change_7d_pct": 0.0,
                "signal": SIGNAL_BUY,
                "price": 1.0,
                "confidence_ok": True,
                "conformal_ok": True,
            },
            {
                "id": "b",
                "name": "B",
                "expected_change_pct": 1.0,
                "price_change_7d_pct": 0.0,
                "signal": SIGNAL_HOLD,
                "price": 1.0,
                "confidence_ok": True,
                "conformal_ok": True,
            },
        ]
    )
    watch = pd.DataFrame(
        [
            {"user_id": "u1", "card_id": "a", "name": "A"},
            {"user_id": "u2", "card_id": "a", "name": "A"},
            {"user_id": "u2", "card_id": "b", "name": "B"},
        ]
    )
    import database

    monkeypatch.setattr(database, "load_all_watchlists", lambda: watch)
    alerts = collect_aggregated_sure_alerts(market, threshold_pct=5.0, sure_only=True)
    assert [a.card_id for a in alerts] == ["a"]

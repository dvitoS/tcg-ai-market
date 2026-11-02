"""Sure-only alert gate: conformal + actionable signal."""

from __future__ import annotations

import pandas as pd

from services.alerts import collect_watchlist_alerts, is_sure_alert
from services.email_alerts import default_sure_only, format_digest
from trading_signals import SIGNAL_BUY, SIGNAL_HOLD, SIGNAL_SELL


def test_is_sure_alert_requires_conformal_and_action():
    assert (
        is_sure_alert(
            signal=SIGNAL_BUY,
            conformal_ok=True,
            confidence_ok=True,
            reason="ai",
        )
        is True
    )
    assert (
        is_sure_alert(
            signal=SIGNAL_BUY,
            conformal_ok=False,
            confidence_ok=True,
            reason="ai",
        )
        is False
    )
    assert (
        is_sure_alert(
            signal=SIGNAL_HOLD,
            conformal_ok=True,
            confidence_ok=True,
            reason="ai",
        )
        is False
    )
    assert (
        is_sure_alert(
            signal=SIGNAL_SELL,
            conformal_ok=True,
            confidence_ok=True,
            reason="price",
        )
        is False
    )


def test_collect_sure_only_drops_price_and_uncertain():
    market = pd.DataFrame(
        [
            {
                "id": "sure_buy",
                "name": "Sure",
                "expected_change_pct": 10.0,
                "price_change_7d_pct": 1.0,
                "signal": SIGNAL_BUY,
                "price": 2.0,
                "confidence_ok": True,
                "conformal_ok": True,
            },
            {
                "id": "wide",
                "name": "Wide",
                "expected_change_pct": 12.0,
                "price_change_7d_pct": 0.0,
                "signal": SIGNAL_BUY,
                "price": 3.0,
                "confidence_ok": True,
                "conformal_ok": False,
            },
            {
                "id": "price_only",
                "name": "Pump",
                "expected_change_pct": 0.5,
                "price_change_7d_pct": -9.0,
                "signal": SIGNAL_HOLD,
                "price": 4.0,
                "confidence_ok": True,
                "conformal_ok": True,
            },
        ]
    )
    watch = pd.DataFrame(
        [
            {"card_id": "sure_buy", "name": "Sure"},
            {"card_id": "wide", "name": "Wide"},
            {"card_id": "price_only", "name": "Pump"},
        ]
    )
    all_alerts = collect_watchlist_alerts(
        market, watch, threshold_pct=5.0, dismissed=set(), sure_only=False
    )
    assert {a.card_id for a in all_alerts} == {"sure_buy", "wide", "price_only"}
    assert all_alerts[0].card_id == "sure_buy"
    assert all_alerts[0].sure is True

    sure = collect_watchlist_alerts(
        market, watch, threshold_pct=5.0, dismissed=set(), sure_only=True
    )
    assert [a.card_id for a in sure] == ["sure_buy"]


def test_format_digest_sure_mode_header():
    body = format_digest([], threshold_pct=5.0, sure_only=True)
    assert "sure-only" in body.lower()


def test_default_sure_only_true(monkeypatch):
    import services.email_alerts as email_alerts

    monkeypatch.setattr(email_alerts, "_clean", lambda name: "")
    assert default_sure_only() is True
    monkeypatch.setattr(
        email_alerts, "_clean", lambda name: "0" if name == "ALERT_SURE_ONLY" else ""
    )
    assert default_sure_only() is False

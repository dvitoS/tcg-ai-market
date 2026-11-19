"""Asking match-quality classifier (T0.1)."""

from __future__ import annotations

from services.spot_match import classify_spot_match


def test_low_when_quarantined():
    out = classify_spot_match(
        tcgplayer_id="123456",
        spot_quarantine=True,
        history_points=40,
    )
    assert out["quality"] == "low"
    assert out["reason"] == "quarantine"


def test_low_when_no_tcp():
    out = classify_spot_match(tcgplayer_id=None, history_points=40)
    assert out["quality"] == "low"
    assert out["reason"] == "no_tcp"


def test_med_thin_history():
    out = classify_spot_match(
        tcgplayer_id="624679",
        spot_quarantine=False,
        history_points=5,
    )
    assert out["quality"] == "med"
    assert out["reason"] == "thin_history"
    assert out["tcgplayer_id"] == "624679"


def test_high_linked():
    out = classify_spot_match(
        tcgplayer_id="624679",
        spot_quarantine=False,
        history_points=20,
    )
    assert out["quality"] == "high"
    assert out["reason"] == "linked"


def test_strips_non_digits_tcp():
    out = classify_spot_match(tcgplayer_id="tcp:624679", history_points=20)
    assert out["quality"] == "high"
    assert out["tcgplayer_id"] == "624679"

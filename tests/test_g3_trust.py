"""G3 trust gate — wrong-price cancel/refund classification."""

from __future__ import annotations

from services.g3_trust import (
    extract_cancel_reason,
    g3_trust_snapshot,
    looks_like_wrong_price,
    record_cancel_or_refund,
    reset_g3_trust_for_tests,
)


def test_looks_like_wrong_price_keywords() -> None:
    assert looks_like_wrong_price("wrong price on Radar")
    assert looks_like_wrong_price("Krivi spot na karti")
    assert looks_like_wrong_price("spot is off vs TCP")
    assert not looks_like_wrong_price("too expensive for me")
    assert not looks_like_wrong_price("")


def test_extract_cancel_reason_from_metadata() -> None:
    reason = extract_cancel_reason(
        {"metadata": {"cancel_reason": "wrong prices everywhere"}}
    )
    assert reason == "wrong prices everywhere"


def test_g3_gate_blocks_when_wrong_price_share_high() -> None:
    reset_g3_trust_for_tests()
    record_cancel_or_refund(kind="cancel", reason="wrong price", event_type="subscription.canceled")
    record_cancel_or_refund(kind="refund", reason="changed mind", event_type="refund.created")
    snap = g3_trust_snapshot(entitled=10, canceled=2, spot_reports_open=1, spot_reports_total=1)
    assert snap["cited_total"] == 2
    assert snap["wrong_price_hits"] == 1
    assert snap["wrong_price_pct"] == 50.0
    assert snap["gate_ok"] is False


def test_g3_gate_ok_when_under_target() -> None:
    reset_g3_trust_for_tests()
    for _ in range(50):
        record_cancel_or_refund(kind="cancel", reason="budget", event_type="subscription.canceled")
    record_cancel_or_refund(kind="cancel", reason="wrong price", event_type="subscription.canceled")
    snap = g3_trust_snapshot(entitled=20, canceled=5, spot_reports_open=0, spot_reports_total=0)
    assert snap["wrong_price_pct"] == round(100.0 / 51, 2)
    assert snap["gate_ok"] is True


def test_conversion_summary_includes_g3(monkeypatch) -> None:
    from services.pro_entitlements import conversion_summary

    reset_g3_trust_for_tests()
    monkeypatch.setattr(
        "services.pro_entitlements.entitlement_status_counts",
        lambda: {"active": 2, "trialing": 1, "canceled": 1},
    )
    monkeypatch.setattr(
        "services.spot_reports.spot_report_summary",
        lambda: {"open_total": 1, "counts": {"open": 1}},
    )
    summary = conversion_summary()
    assert "g3_trust" in summary
    assert summary["g3_trust"]["entitled"] == 3
    assert summary["g3_trust"]["spot_reports_open"] == 1

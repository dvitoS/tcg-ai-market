"""Trial → paid conversion summary (M4.3)."""

from __future__ import annotations

from services.pro_entitlements import conversion_summary
from services.trial_hygiene import (
    record_webhook_outcome,
    reset_webhook_outcomes_for_tests,
)


def test_conversion_summary_paid_share(monkeypatch):
    from services.g3_trust import reset_g3_trust_for_tests

    reset_webhook_outcomes_for_tests()
    reset_g3_trust_for_tests()
    record_webhook_outcome(
        action="grant", status="trialing", event_type="subscription.trialing"
    )
    record_webhook_outcome(
        action="grant", status="active", event_type="subscription.paid"
    )

    monkeypatch.setattr(
        "services.pro_entitlements.entitlement_status_counts",
        lambda: {"active": 3, "trialing": 1, "canceled": 2},
    )
    monkeypatch.setattr(
        "services.spot_reports.spot_report_summary",
        lambda: {"open_total": 0, "counts": {}, "overdue_heal": 0},
    )
    monkeypatch.setattr(
        "services.spot_qa.load_spot_qa_snapshot",
        lambda: {"nightly_auto_g0": {"g0_ready": True}},
    )
    monkeypatch.setattr(
        "services.funnel.funnel_summary",
        lambda: {"counts": {"share_copy": 1}, "total": 1},
    )
    summary = conversion_summary()
    assert summary["active"] == 3
    assert summary["trialing"] == 1
    assert summary["entitled"] == 4
    assert summary["paid_share_pct"] == 75.0
    assert summary["webhook_outcomes"]["counts"]["total"] == 2
    assert summary["g3_trust"]["gate_ok"] is True
    assert summary["spend_unlock"]["ready"] is True
    assert summary["source"] == "supabase"


def test_conversion_summary_empty(monkeypatch):
    from services.g3_trust import reset_g3_trust_for_tests

    reset_webhook_outcomes_for_tests()
    reset_g3_trust_for_tests()
    monkeypatch.setattr(
        "services.pro_entitlements.entitlement_status_counts",
        lambda: {},
    )
    monkeypatch.setattr(
        "services.spot_reports.spot_report_summary",
        lambda: {"open_total": 0, "counts": {}, "overdue_heal": 0},
    )
    monkeypatch.setattr("services.spot_qa.load_spot_qa_snapshot", lambda: None)
    monkeypatch.setattr(
        "services.funnel.funnel_summary",
        lambda: {"counts": {}, "total": 0},
    )
    summary = conversion_summary()
    assert summary["entitled"] == 0
    assert summary["paid_share_pct"] is None
    assert summary["source"] == "empty"
    assert "g3_trust" in summary
    assert "spend_unlock" in summary

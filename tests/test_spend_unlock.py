"""Spend unlock rollup (G0–G3) for Data Health."""

from __future__ import annotations

from services.g3_trust import record_cancel_or_refund, reset_g3_trust_for_tests
from services.spend_unlock import spend_unlock_snapshot


def test_spend_unlock_blocks_on_g3_wrong_price(monkeypatch) -> None:
    reset_g3_trust_for_tests()
    record_cancel_or_refund(kind="cancel", reason="wrong price")
    record_cancel_or_refund(kind="refund", reason="budget")

    monkeypatch.setattr(
        "services.spot_qa.load_spot_qa_snapshot",
        lambda: {
            "nightly_auto_g0": {
                "g0_ready": True,
                "captured_at": "2026-11-19T00:00:00+00:00",
                "verdict_pass": 10,
                "verdict_fail": 0,
            }
        },
    )
    monkeypatch.setattr(
        "services.funnel.funnel_summary",
        lambda: {"counts": {"share_copy": 2, "share_png": 1}, "total": 3},
    )
    monkeypatch.setattr(
        "services.spot_reports.spot_report_summary",
        lambda: {"overdue_heal": 0, "open_total": 0},
    )

    snap = spend_unlock_snapshot()
    assert snap["g0"]["status"] == "green"
    assert snap["g2"]["status"] == "green"
    assert snap["g2"]["share_events"] == 3
    assert snap["g3"]["status"] == "red"
    assert "g3_wrong_price_gate" in snap["blockers"]
    assert snap["ready"] is False


def test_spend_unlock_ready_when_gates_green(monkeypatch) -> None:
    reset_g3_trust_for_tests()
    for _ in range(50):
        record_cancel_or_refund(kind="cancel", reason="budget")

    monkeypatch.setattr(
        "services.spot_qa.load_spot_qa_snapshot",
        lambda: {
            "nightly_auto_g0": {
                "g0_ready": True,
                "captured_at": "2026-11-19T00:00:00+00:00",
                "verdict_pass": 12,
                "verdict_fail": 0,
            }
        },
    )
    monkeypatch.setattr(
        "services.funnel.funnel_summary",
        lambda: {"counts": {"share_copy": 1}, "total": 1},
    )
    monkeypatch.setattr(
        "services.spot_reports.spot_report_summary",
        lambda: {"overdue_heal": 0, "open_total": 0},
    )

    snap = spend_unlock_snapshot()
    assert snap["g3"]["gate_ok"] is True
    assert snap["g3"]["status"] == "green"
    assert snap["ready"] is True
    assert snap["status"] == "green"


def test_conversion_summary_includes_spend_unlock(monkeypatch) -> None:
    from services.pro_entitlements import conversion_summary

    reset_g3_trust_for_tests()
    monkeypatch.setattr(
        "services.pro_entitlements.entitlement_status_counts",
        lambda: {"active": 1, "trialing": 1},
    )
    monkeypatch.setattr(
        "services.spot_reports.spot_report_summary",
        lambda: {"open_total": 0, "counts": {}, "overdue_heal": 0},
    )
    monkeypatch.setattr(
        "services.spot_qa.load_spot_qa_snapshot",
        lambda: {"nightly_auto_g0": {"g0_ready": False}},
    )
    monkeypatch.setattr(
        "services.funnel.funnel_summary",
        lambda: {"counts": {}, "total": 0},
    )
    summary = conversion_summary()
    assert "spend_unlock" in summary
    assert summary["spend_unlock"]["g0"]["status"] == "red"
    assert summary["spend_unlock"]["ready"] is False

"""Marketing spend unlock rollup (G0–G3) for Data Health.

G1 stays manual (cold-user checklist). G2 uses share funnel as a soft proxy
— external posts still required per ``docs/G2_SHARE_CHECKLIST.md``.
"""

from __future__ import annotations

from typing import Any


def spend_unlock_snapshot(
    *,
    g3: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose a single ops-facing spend unlock card."""
    from services.funnel import funnel_summary
    from services.spot_qa import load_spot_qa_snapshot
    from services.spot_reports import spot_report_summary

    if g3 is None:
        from services.g3_trust import g3_trust_snapshot

        g3 = g3_trust_snapshot()

    qa = load_spot_qa_snapshot() or {}
    nightly = qa.get("nightly_auto_g0") if isinstance(qa.get("nightly_auto_g0"), dict) else {}
    g0_ready = bool(nightly.get("g0_ready")) if nightly else None
    g0_status = "unknown"
    if nightly:
        g0_status = "green" if g0_ready else "red"
    elif qa.get("g0_ready") is True:
        g0_status = "green"
        g0_ready = True
    elif qa.get("g0_ready") is False:
        g0_status = "red"
        g0_ready = False

    funnel = funnel_summary()
    counts = funnel.get("counts") if isinstance(funnel.get("counts"), dict) else {}
    share_n = int(counts.get("share_copy") or 0) + int(counts.get("share_png") or 0)
    g2_status = "green" if share_n > 0 else "yellow"

    gate_ok = bool(g3.get("gate_ok"))
    cited = int(g3.get("cited_total") or 0)
    g3_status = "green" if gate_ok and cited > 0 else ("yellow" if gate_ok else "red")

    try:
        reports = spot_report_summary()
        overdue = int(reports.get("overdue_heal") or 0)
    except Exception:
        overdue = 0

    blockers: list[str] = []
    if g0_status == "red":
        blockers.append("g0_nightly_not_ready")
    if g0_status == "unknown":
        blockers.append("g0_nightly_missing")
    if g3_status == "red":
        blockers.append("g3_wrong_price_gate")
    if overdue > 0:
        blockers.append("wrong_spot_sla_overdue")
    if share_n == 0:
        blockers.append("g2_no_share_events_yet")

    # Unlock needs G0 green + G3 not blocked; G1/G2 remain ops/manual.
    ready = g0_status == "green" and g3_status != "red" and overdue == 0

    return {
        "ready": ready,
        "status": "green" if ready else ("yellow" if not blockers or blockers == ["g2_no_share_events_yet"] else "red"),
        "blockers": blockers,
        "g0": {
            "status": g0_status,
            "ready": g0_ready,
            "captured_at": nightly.get("captured_at") or qa.get("captured_at"),
            "verdict_pass": nightly.get("verdict_pass"),
            "verdict_fail": nightly.get("verdict_fail"),
        },
        "g1": {
            "status": "manual",
            "checklist": "docs/G1_COLD_USER_CHECKLIST.md",
        },
        "g2": {
            "status": g2_status,
            "share_events": share_n,
            "note": "External ≥1/week post still required — docs/G2_SHARE_CHECKLIST.md",
        },
        "g3": {
            "status": g3_status,
            "gate_ok": gate_ok,
            "wrong_price_pct": g3.get("wrong_price_pct"),
            "cited_total": cited,
            "persisted": bool(g3.get("persisted")),
            "source": g3.get("source"),
        },
        "docs": {
            "g3": "docs/G3_METRICS_CHECKLIST.md",
            "organic": "docs/ORGANIC_SOFT_LAUNCH.md",
        },
    }

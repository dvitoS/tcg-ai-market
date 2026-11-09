"""Persist Kestrel Pro grants (Creem webhooks + manual ops)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

LOG = logging.getLogger("kestrel.pro_entitlements")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client():
    from database_clients import get_supabase

    return get_supabase()


_PRO_LIVE_STATUSES = ("active", "trialing")


def email_has_active_pro(email: str | None) -> bool:
    """True when ``pro_entitlements`` has an active or trialing row for this email."""
    key = str(email or "").strip().lower()
    if not key:
        return False
    try:
        res = (
            _client()
            .table("pro_entitlements")
            .select("id,status")
            .eq("email", key)
            .in_("status", list(_PRO_LIVE_STATUSES))
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        return bool(rows)
    except Exception as exc:
        LOG.info("pro_entitlements lookup skipped: %s", exc)
        return False


def user_id_has_active_pro(user_id: str | None) -> bool:
    uid = str(user_id or "").strip()
    if not uid:
        return False
    try:
        res = (
            _client()
            .table("pro_entitlements")
            .select("id,status")
            .eq("user_id", uid)
            .in_("status", list(_PRO_LIVE_STATUSES))
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        return bool(rows)
    except Exception as exc:
        LOG.info("pro_entitlements user lookup skipped: %s", exc)
        return False


def entitlement_status_counts() -> dict[str, int]:
    """Count rows by status for the trial→paid ops dashboard."""
    try:
        res = (
            _client()
            .table("pro_entitlements")
            .select("status")
            .execute()
        )
        rows = getattr(res, "data", None) or []
    except Exception as exc:
        LOG.info("pro_entitlements status counts skipped: %s", exc)
        return {}
    counts: dict[str, int] = {}
    for row in rows:
        key = str((row or {}).get("status") or "unknown").strip() or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def conversion_summary() -> dict[str, Any]:
    """Trial hygiene snapshot from ``pro_entitlements`` (+ process webhook counters)."""
    from services.g3_trust import g3_trust_snapshot
    from services.spot_reports import spot_report_summary
    from services.trial_hygiene import webhook_outcome_counts

    by_status = entitlement_status_counts()
    active = int(by_status.get("active") or 0)
    trialing = int(by_status.get("trialing") or 0)
    canceled = int(by_status.get("canceled") or 0)
    expired = int(by_status.get("expired") or 0)
    past_due = int(by_status.get("past_due") or 0)
    entitled = active + trialing
    paid_share_pct = (
        round(100.0 * active / entitled, 1) if entitled > 0 else None
    )
    try:
        reports = spot_report_summary()
    except Exception:
        reports = {"open_total": 0, "counts": {}}
    report_counts = reports.get("counts") if isinstance(reports, dict) else {}
    if not isinstance(report_counts, dict):
        report_counts = {}
    spot_total = sum(int(v or 0) for v in report_counts.values())
    g3 = g3_trust_snapshot(
        entitled=entitled,
        canceled=canceled,
        spot_reports_open=int(reports.get("open_total") or 0),
        spot_reports_total=spot_total,
    )
    return {
        "by_status": by_status,
        "active": active,
        "trialing": trialing,
        "canceled": canceled,
        "expired": expired,
        "past_due": past_due,
        "entitled": entitled,
        "paid_share_pct": paid_share_pct,
        "webhook_outcomes": webhook_outcome_counts(),
        "g3_trust": g3,
        "source": "supabase" if by_status else "empty",
    }


def grant_pro_entitlement(
    *,
    email: str,
    user_id: str | None = None,
    status: str = "active",
    source: str = "creem",
    creem_customer_id: str | None = None,
    creem_subscription_id: str | None = None,
    creem_product_id: str | None = None,
    creem_order_id: str | None = None,
    creem_checkout_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Upsert an entitlement keyed by lower(email). Returns stored row or None."""
    key = str(email or "").strip().lower()
    if not key:
        LOG.warning("grant_pro_entitlement called without email")
        return None

    row: dict[str, Any] = {
        "email": key,
        "status": status or "active",
        "source": source or "creem",
        "updated_at": _now_iso(),
        "metadata": metadata or {},
    }
    if user_id:
        row["user_id"] = str(user_id).strip()
    if creem_customer_id:
        row["creem_customer_id"] = creem_customer_id
    if creem_subscription_id:
        row["creem_subscription_id"] = creem_subscription_id
    if creem_product_id:
        row["creem_product_id"] = creem_product_id
    if creem_order_id:
        row["creem_order_id"] = creem_order_id
    if creem_checkout_id:
        row["creem_checkout_id"] = creem_checkout_id

    # Prefer insert → update: more reliable than PostgREST on_conflict with
    # a unique index that may not be exposed as a constraint name.
    merged = _grant_manual_merge(row)
    if merged is not None:
        return merged
    try:
        res = (
            _client()
            .table("pro_entitlements")
            .upsert(row, on_conflict="email")
            .execute()
        )
        data = getattr(res, "data", None) or []
        return data[0] if data else row
    except Exception as exc:
        LOG.exception("pro_entitlements upsert failed for %s: %s", key, exc)
        return None


def _grant_manual_merge(row: dict[str, Any]) -> dict[str, Any] | None:
    email = row["email"]
    try:
        client = _client()
        existing = (
            client.table("pro_entitlements")
            .select("id")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        found = getattr(existing, "data", None) or []
        if found:
            res = (
                client.table("pro_entitlements")
                .update(row)
                .eq("email", email)
                .execute()
            )
        else:
            res = client.table("pro_entitlements").insert(row).execute()
        data = getattr(res, "data", None) or []
        return data[0] if data else row
    except Exception as exc:
        LOG.exception("pro_entitlements grant failed for %s: %s", email, exc)
        return None


def set_entitlement_status_by_subscription(
    *,
    subscription_id: str,
    status: str,
) -> int:
    """Update rows matching a Creem subscription id. Returns updated count."""
    sid = str(subscription_id or "").strip()
    if not sid:
        return 0
    try:
        res = (
            _client()
            .table("pro_entitlements")
            .update({"status": status, "updated_at": _now_iso()})
            .eq("creem_subscription_id", sid)
            .execute()
        )
        data = getattr(res, "data", None) or []
        return len(data)
    except Exception as exc:
        LOG.exception("pro_entitlements status update failed: %s", exc)
        return 0

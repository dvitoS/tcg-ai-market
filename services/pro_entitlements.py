"""Persist Soft Pro grants (Creem webhooks + manual ops)."""

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


def email_has_active_pro(email: str | None) -> bool:
    """True when ``pro_entitlements`` has an active row for this email."""
    key = str(email or "").strip().lower()
    if not key:
        return False
    try:
        res = (
            _client()
            .table("pro_entitlements")
            .select("id,status")
            .eq("email", key)
            .eq("status", "active")
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
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        return bool(rows)
    except Exception as exc:
        LOG.info("pro_entitlements user lookup skipped: %s", exc)
        return False


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
        # Unique index is on lower(email); PostgREST upsert needs a UNIQUE
        # constraint name. Fall back to select+update/insert when needed.
        LOG.info("pro_entitlements upsert failed (%s); trying manual merge", exc)
        return _grant_manual_merge(row)


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

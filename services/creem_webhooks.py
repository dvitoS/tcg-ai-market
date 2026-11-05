"""Creem webhook verification + Kestrel Pro grant handlers."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any

from config import _secret

LOG = logging.getLogger("kestrel.creem")

GRANT_EVENTS = frozenset(
    {
        "checkout.completed",
        "subscription.active",
        "subscription.paid",
        "subscription.trialing",
    }
)
REVOKE_EVENTS = frozenset(
    {
        "subscription.canceled",
        "subscription.expired",
        "subscription.unpaid",
        "subscription.past_due",
    }
)


def creem_webhook_secret() -> str:
    from config import _clean_secret_value

    # Accept the documented name; also tolerate a common typo used in dashboards.
    for name in ("CREEM_WEBHOOK_SECRET", "CREEM_WEBHOOK_SECRETS", "CREEM_SIGNING_SECRET"):
        raw = _secret(name) or os.getenv(name, "") or ""
        cleaned = _clean_secret_value(str(raw))
        if cleaned:
            return cleaned
    return ""


def verify_creem_signature(raw_body: bytes | str, signature: str | None, secret: str | None = None) -> bool:
    """HMAC-SHA256 hex digest over the raw body vs ``creem-signature`` header."""
    key = (secret if secret is not None else creem_webhook_secret()).strip()
    sig = str(signature or "").strip()
    if not key or not sig:
        return False
    payload = raw_body if isinstance(raw_body, (bytes, bytearray)) else str(raw_body).encode("utf-8")
    digest = hmac.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(digest, sig)
    except (TypeError, ValueError):
        return False


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _email_from_object(obj: dict[str, Any]) -> str | None:
    """Best-effort customer email from Creem checkout / subscription payloads."""
    customer = obj.get("customer")
    if isinstance(customer, dict):
        email = str(customer.get("email") or "").strip().lower()
        if email:
            return email
    # Some payloads nest customer under order or subscription.
    for nest_key in ("order", "subscription"):
        nested = _as_dict(obj.get(nest_key))
        nested_customer = nested.get("customer")
        if isinstance(nested_customer, dict):
            email = str(nested_customer.get("email") or "").strip().lower()
            if email:
                return email
    meta = _as_dict(obj.get("metadata"))
    for key in ("email", "user_email", "customer_email"):
        alt = str(meta.get(key) or "").strip().lower()
        if alt:
            return alt
    return None


def _id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        raw = value.get("id")
        return str(raw).strip() if raw else None
    text = str(value).strip()
    return text or None


def handle_creem_event(event: dict[str, Any]) -> dict[str, Any]:
    """Apply Pro grant/revoke for a verified Creem webhook payload."""
    from services import pro_entitlements as entitlements

    event_type = str(event.get("eventType") or event.get("event_type") or "").strip()
    obj = _as_dict(event.get("object"))
    email = _email_from_object(obj)
    product = _as_dict(obj.get("product"))
    order = _as_dict(obj.get("order"))
    subscription = _as_dict(obj.get("subscription"))
    customer = _as_dict(obj.get("customer"))
    metadata = _as_dict(obj.get("metadata"))

    user_id = str(metadata.get("user_id") or metadata.get("userId") or "").strip() or None
    product_id = _id(product) or _id(obj.get("product_id")) or _id(order.get("product"))
    subscription_id = _id(subscription) or _id(obj.get("subscription_id"))
    customer_id = _id(customer) or _id(obj.get("customer_id"))
    order_id = _id(order)
    checkout_id = _id(obj) if obj.get("object") == "checkout" else _id(obj.get("id"))

    if event_type in GRANT_EVENTS:
        if not email:
            LOG.warning("Creem %s missing customer email", event_type)
            return {"ok": False, "reason": "missing_email", "event_type": event_type}
        row = entitlements.grant_pro_entitlement(
            email=email,
            user_id=user_id,
            status="active",
            source="creem",
            creem_customer_id=customer_id,
            creem_subscription_id=subscription_id,
            creem_product_id=product_id,
            creem_order_id=order_id,
            creem_checkout_id=checkout_id,
            metadata={"event_type": event_type, **metadata},
        )
        return {
            "ok": bool(row),
            "action": "grant",
            "event_type": event_type,
            "email": email,
        }

    if event_type in REVOKE_EVENTS:
        status_map = {
            "subscription.canceled": "canceled",
            "subscription.expired": "expired",
            "subscription.unpaid": "past_due",
            "subscription.past_due": "past_due",
        }
        status = status_map.get(event_type, "canceled")
        if subscription_id:
            n = entitlements.set_entitlement_status_by_subscription(
                subscription_id=subscription_id,
                status=status,
            )
            return {
                "ok": True,
                "action": "revoke",
                "event_type": event_type,
                "updated": n,
                "subscription_id": subscription_id,
            }
        if email:
            row = entitlements.grant_pro_entitlement(
                email=email,
                user_id=user_id,
                status=status,
                source="creem",
                creem_customer_id=customer_id,
                creem_subscription_id=subscription_id,
                creem_product_id=product_id,
                metadata={"event_type": event_type, **metadata},
            )
            return {
                "ok": bool(row),
                "action": "revoke",
                "event_type": event_type,
                "email": email,
            }
        return {"ok": False, "reason": "missing_subscription_or_email", "event_type": event_type}

    return {"ok": True, "action": "ignored", "event_type": event_type or "unknown"}

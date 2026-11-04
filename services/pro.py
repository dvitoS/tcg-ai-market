"""Soft Pro entitlement (Creem + env allowlist).

- ``PRO_OPEN=1`` (default) → everyone is Pro (open beta).
- ``PRO_OPEN=0`` → require env allowlist and/or ``pro_entitlements`` (Creem webhook).
- Local ``AUTH_DISABLED`` → always Pro.
- ``PRO_OPEN=0`` with empty allowlist **and** Creem not wired → stay open
  (avoid locking everyone out before checkout/webhook exist).
- Once ``PRO_CHECKOUT_URL`` or ``CREEM_WEBHOOK_SECRET`` is set, unpaid users lock.
"""

from __future__ import annotations

import os
from typing import Any

from config import _secret, auth_disabled


def _clean(name: str) -> str:
    return str(_secret(name) or os.getenv(name, "") or "").strip()


def _flag_on(raw: str, *, default: bool) -> bool:
    text = (raw or "").strip().lower()
    if not text:
        return default
    return text not in {"0", "false", "no", "off"}


def _split_list(raw: str) -> set[str]:
    out: set[str] = set()
    for chunk in (raw or "").replace(";", ",").split(","):
        item = chunk.strip().lower()
        if item:
            out.add(item)
    return out


def pro_open_beta() -> bool:
    return _flag_on(_clean("PRO_OPEN"), default=True)


def pro_allowlist_emails() -> set[str]:
    return _split_list(_clean("PRO_EMAILS"))


def pro_allowlist_user_ids() -> set[str]:
    return _split_list(_clean("PRO_USER_IDS"))


def has_pro_allowlist() -> bool:
    return bool(pro_allowlist_emails() or pro_allowlist_user_ids())


def pro_checkout_url() -> str | None:
    """Creem payment link (or any https checkout). None when unset."""
    url = _clean("PRO_CHECKOUT_URL")
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return None


def pro_portal_url() -> str | None:
    """Optional Creem customer portal / manage-subscription link."""
    url = _clean("CREEM_PORTAL_URL") or _clean("PRO_PORTAL_URL")
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return None


def creem_enforcement_ready() -> bool:
    """True when Creem is wired enough that unpaid users should be locked."""
    if pro_checkout_url():
        return True
    try:
        from services.creem_webhooks import creem_webhook_secret

        if creem_webhook_secret():
            return True
    except Exception:
        pass
    return False


def _resolve_user(user: dict[str, Any] | None) -> dict[str, Any]:
    if user is not None:
        return user
    try:
        import auth as auth_mod

        return auth_mod.current_user() or {}
    except Exception:
        return {}


def _db_entitlement(email: str, uid: str) -> bool:
    try:
        from services import pro_entitlements as entitlements

        if email and entitlements.email_has_active_pro(email):
            return True
        if uid and entitlements.user_id_has_active_pro(uid):
            return True
    except Exception:
        return False
    return False


def is_pro_user(user: dict[str, Any] | None = None) -> bool:
    """True when the user may use Dealer desk + sure-only Pro surfaces."""
    if auth_disabled():
        return True
    if pro_open_beta():
        return True

    raw = _resolve_user(user)
    email = str((raw or {}).get("email") or "").strip().lower()
    uid = str((raw or {}).get("id") or "").strip().lower()
    if email and email in pro_allowlist_emails():
        return True
    if uid and uid in pro_allowlist_user_ids():
        return True
    if _db_entitlement(email, uid):
        return True

    # Stay open only until Creem (or a manual allowlist) is configured.
    if not has_pro_allowlist() and not creem_enforcement_ready():
        return True
    return False


def pro_gate_reason(user: dict[str, Any] | None = None) -> str:
    if auth_disabled():
        return "dev"
    if pro_open_beta():
        return "open_beta"

    raw = _resolve_user(user)
    email = str((raw or {}).get("email") or "").strip().lower()
    uid = str((raw or {}).get("id") or "").strip().lower()

    if email and email in pro_allowlist_emails():
        return "allowlist"
    if uid and uid in pro_allowlist_user_ids():
        return "allowlist"
    if _db_entitlement(email, uid):
        return "entitlement"
    if auth_disabled() or (raw or {}).get("dev"):
        return "dev"
    if not has_pro_allowlist() and not creem_enforcement_ready():
        return "open_beta"
    if is_pro_user(raw):
        return "pro"
    return "locked"


def billing_snapshot(user: dict[str, Any] | None = None) -> dict[str, Any]:
    """Public + per-user Soft Pro status for Soft Ink billing UI."""
    raw = _resolve_user(user) if user is not None else (user or {})
    authenticated = bool(raw and (raw.get("id") or raw.get("email")))
    allowed = bool(is_pro_user(raw if authenticated else None)) if authenticated else False
    # Anonymous callers still learn open-beta / checkout without claiming Pro.
    if not authenticated:
        allowed = bool(pro_open_beta() or auth_disabled())
    return {
        "pro_open": bool(pro_open_beta()),
        "is_pro": allowed,
        "reason": pro_gate_reason(raw if authenticated else None),
        "checkout_url": pro_checkout_url(),
        "portal_url": pro_portal_url(),
        "authenticated": authenticated,
        "email": str(raw.get("email") or "") if authenticated else None,
        "enforcement_ready": bool(creem_enforcement_ready() or has_pro_allowlist()),
    }


def render_pro_upgrade_cta(*, key: str = "pro_upgrade") -> None:
    """Legacy Streamlit CTA helper (no Soft Ink UI). Safe no-op without Streamlit."""
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        if get_script_run_ctx() is None:
            return
    except Exception:
        return

    from i18n import t

    checkout = pro_checkout_url()
    if checkout:
        st.link_button(
            t("pro_upgrade_cta"),
            checkout,
            type="primary",
            use_container_width=True,
            key=f"{key}_link",
        )
        st.caption(t("pro_upgrade_after_pay"))
    else:
        st.caption(t("pro_upgrade_hint"))

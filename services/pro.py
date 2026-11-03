"""Soft Pro entitlement (Creem + env allowlist).

- ``PRO_OPEN=1`` (default) → everyone is Pro (open beta).
- ``PRO_OPEN=0`` → require env allowlist and/or ``pro_entitlements`` (Creem webhook).
- Local ``AUTH_DISABLED`` → always Pro.
- ``PRO_OPEN=0`` with empty allowlist and no DB grants → stay open
  (avoid locking everyone out before Creem is wired).
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

    # No env allowlist and no DB hit → stay open until Creem grants exist.
    if not has_pro_allowlist():
        return True
    return False


def pro_gate_reason() -> str:
    if auth_disabled():
        return "dev"
    if pro_open_beta():
        return "open_beta"
    if is_pro_user():
        return "allowlist"
    if not has_pro_allowlist():
        return "open_beta"
    return "locked"


def pro_checkout_url() -> str | None:
    """Creem payment link (or any https checkout). None when unset."""
    url = _clean("PRO_CHECKOUT_URL")
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return None


def render_pro_upgrade_cta(*, key: str = "pro_upgrade") -> None:
    """Locked-surface CTA: checkout link when configured, else ops hint."""
    import streamlit as st

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

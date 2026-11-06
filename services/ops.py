"""Soft Ink operator allowlist — System status / data-health only."""

from __future__ import annotations

import os
from typing import Any

from config import _secret

# Solo Soft Ink fallback when OPS_EMAILS is unset (override via env).
_DEFAULT_OPS_EMAILS = {"vitoskender@gmail.com"}


def _clean(name: str) -> str:
    return str(_secret(name) or os.getenv(name, "") or "").strip()


def _split_list(raw: str) -> set[str]:
    out: set[str] = set()
    for chunk in (raw or "").replace(";", ",").split(","):
        item = chunk.strip().lower()
        if item:
            out.add(item)
    return out


def ops_allowlist_emails() -> set[str]:
    configured = _split_list(_clean("OPS_EMAILS"))
    return configured or set(_DEFAULT_OPS_EMAILS)


def ops_allowlist_user_ids() -> set[str]:
    return _split_list(_clean("OPS_USER_IDS"))


def is_ops_user(user: dict[str, Any] | None) -> bool:
    """True for local demo ``dev`` users or OPS_EMAILS / OPS_USER_IDS matches.

    Never trust a client-supplied ``ops`` flag — recompute from identity.
    """
    if not user:
        return False
    if user.get("dev"):
        return True
    email = str(user.get("email") or "").strip().lower()
    uid = str(user.get("id") or "").strip().lower()
    if email and email in ops_allowlist_emails():
        return True
    if uid and uid in ops_allowlist_user_ids():
        return True
    return False


def with_ops_flag(user: dict[str, Any]) -> dict[str, Any]:
    """Copy user dict and set ``ops`` from the allowlist (never trust client)."""
    out = {k: v for k, v in user.items() if k != "ops"}
    out["ops"] = is_ops_user(out)
    return out

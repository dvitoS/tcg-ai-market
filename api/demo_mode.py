"""Local / CI demo mode when Auth is disabled or Supabase is unavailable."""

from __future__ import annotations

import os

from config import _clean_secret_value, _secret, auth_disabled, get_supabase_auth_credentials


def _flag(name: str) -> bool:
    raw = _clean_secret_value(_secret(name) or os.getenv(name, "") or "").lower()
    return raw in {"1", "true", "yes", "on"}


def supabase_auth_configured() -> bool:
    url, key = get_supabase_auth_credentials()
    return bool(url and key)


def demo_mode() -> bool:
    """True for local Soft Ink demos without multi-user Supabase Auth."""
    if auth_disabled():
        return True
    if _flag("KESTREL_PORTFOLIO_DEMO"):
        return True
    return not supabase_auth_configured()

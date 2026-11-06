"""Auth dependencies for FastAPI (Supabase JWT via anon key)."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status
from supabase import Client, create_client

from config import DEV_USER_EMAIL, DEV_USER_ID, get_supabase_auth_credentials, normalize_supabase_url

from api.demo_mode import demo_mode
from services.ops import is_ops_user, with_ops_flag

LOG = logging.getLogger("kestrel.api.auth")

DEV_TOKEN = "dev-local-token"


def auth_client() -> Client:
    url, key = get_supabase_auth_credentials()
    if not url or not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase auth is not configured (SUPABASE_URL + SUPABASE_ANON_KEY).",
        )
    return create_client(normalize_supabase_url(url), key)


def _dev_user() -> dict[str, Any]:
    return with_ops_flag(
        {"id": str(DEV_USER_ID), "email": str(DEV_USER_EMAIL), "dev": True}
    )


def _user_from_payload(payload: Any) -> dict[str, Any] | None:
    if payload is None:
        return None
    if isinstance(payload, dict):
        user_id = str(payload.get("id") or "").strip()
        email = payload.get("email")
        if not user_id:
            return None
        return with_ops_flag(
            {"id": user_id, "email": str(email) if email else None, "dev": False}
        )
    user_id = str(getattr(payload, "id", "") or "").strip()
    if not user_id:
        return None
    email = getattr(payload, "email", None)
    return with_ops_flag(
        {"id": user_id, "email": str(email) if email else None, "dev": False}
    )


def optional_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any] | None:
    """Return current user if Bearer token present; never raises for missing token."""
    if not authorization:
        # Demo Soft Ink local: portfolio pages can auto-session without a token.
        return _dev_user() if demo_mode() else None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return _dev_user() if demo_mode() else None
    raw = token.strip()
    if demo_mode() and raw in {DEV_TOKEN, "demo", "local"}:
        return _dev_user()
    if demo_mode() and not get_supabase_auth_credentials()[0]:
        return _dev_user()
    try:
        client = auth_client()
        result = client.auth.get_user(raw)
        user = getattr(result, "user", None) or (result.get("user") if isinstance(result, dict) else None)
        return _user_from_payload(user)
    except Exception as exc:
        LOG.info("optional_user token rejected: %s", exc)
        if demo_mode():
            return _dev_user()
        return None


def require_user(
    user: Annotated[dict[str, Any] | None, Depends(optional_user)],
) -> dict[str, Any]:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_ops_user(
    user: Annotated[dict[str, Any], Depends(require_user)],
) -> dict[str, Any]:
    """System status / data-health — operator allowlist only."""
    if not is_ops_user(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ops access required.",
        )
    return user

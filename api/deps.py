"""Auth dependencies for FastAPI (Supabase JWT via anon key)."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status
from supabase import Client, create_client

from config import DEV_USER_EMAIL, DEV_USER_ID, auth_disabled, get_supabase_auth_credentials, normalize_supabase_url

LOG = logging.getLogger("kestrel.api.auth")


def auth_client() -> Client:
    url, key = get_supabase_auth_credentials()
    if not url or not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase auth is not configured (SUPABASE_URL + SUPABASE_ANON_KEY).",
        )
    return create_client(normalize_supabase_url(url), key)


def _user_from_payload(payload: Any) -> dict[str, Any] | None:
    if payload is None:
        return None
    if isinstance(payload, dict):
        user_id = str(payload.get("id") or "").strip()
        email = payload.get("email")
        if not user_id:
            return None
        return {"id": user_id, "email": str(email) if email else None, "dev": False}
    user_id = str(getattr(payload, "id", "") or "").strip()
    if not user_id:
        return None
    email = getattr(payload, "email", None)
    return {"id": user_id, "email": str(email) if email else None, "dev": False}


def optional_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any] | None:
    """Return current user if Bearer token present; never raises for missing token."""
    if auth_disabled():
        return {"id": str(DEV_USER_ID), "email": str(DEV_USER_EMAIL), "dev": True}

    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    try:
        client = auth_client()
        result = client.auth.get_user(token.strip())
        user = getattr(result, "user", None) or (result.get("user") if isinstance(result, dict) else None)
        return _user_from_payload(user)
    except Exception as exc:
        LOG.info("optional_user token rejected: %s", exc)
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

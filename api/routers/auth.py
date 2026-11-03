"""Supabase email/password auth for the web client."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from api.demo_mode import demo_mode
from api.deps import DEV_TOKEN, auth_client, optional_user, require_user
from api.schemas import AuthSessionResponse, AuthUser, LoginRequest, MeResponse
from config import DEV_USER_EMAIL, DEV_USER_ID

LOG = logging.getLogger("kestrel.api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


def _session_payload(session: Any, user: Any) -> AuthSessionResponse:
    if isinstance(session, dict):
        access = str(session.get("access_token") or "")
        refresh = session.get("refresh_token")
    else:
        access = str(getattr(session, "access_token", "") or "")
        refresh = getattr(session, "refresh_token", None)
    if isinstance(user, dict):
        auth_user = AuthUser(
            id=str(user.get("id") or ""),
            email=str(user.get("email") or "") or None,
            dev=bool(user.get("dev")),
        )
    else:
        auth_user = AuthUser(
            id=str(getattr(user, "id", "") or ""),
            email=str(getattr(user, "email", "") or "") or None,
            dev=False,
        )
    if not access or not auth_user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
    return AuthSessionResponse(
        access_token=access,
        refresh_token=str(refresh) if refresh else None,
        user=auth_user,
    )


@router.post("/login", response_model=AuthSessionResponse)
def login(body: LoginRequest) -> AuthSessionResponse:
    if demo_mode():
        return AuthSessionResponse(
            access_token=DEV_TOKEN,
            refresh_token=None,
            user=AuthUser(id=str(DEV_USER_ID), email=body.email.strip() or str(DEV_USER_EMAIL), dev=True),
        )
    try:
        client = auth_client()
        result = client.auth.sign_in_with_password(
            {"email": body.email.strip(), "password": body.password}
        )
    except HTTPException:
        raise
    except Exception as exc:
        LOG.info("login failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        ) from exc

    session = getattr(result, "session", None) or (
        result.get("session") if isinstance(result, dict) else None
    )
    user = getattr(result, "user", None) or (
        result.get("user") if isinstance(result, dict) else None
    )
    if session is None or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return _session_payload(session, user)


@router.get("/me", response_model=MeResponse)
def me(user: Annotated[dict | None, Depends(optional_user)]) -> MeResponse:
    if user is None:
        return MeResponse(authenticated=False, user=None)
    return MeResponse(authenticated=True, user=AuthUser(**user))


@router.post("/logout")
def logout(_user: Annotated[dict, Depends(require_user)]) -> dict[str, bool]:
    # Client drops the Bearer token; optional server-side revoke later.
    return {"ok": True}

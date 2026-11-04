"""Supabase email/password auth for the web client."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status

from api.demo_mode import demo_mode
from api.deps import DEV_TOKEN, auth_client, optional_user, require_user
from api.schemas import (
    AuthSessionResponse,
    AuthUser,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MeResponse,
    SignupRequest,
    SignupResponse,
    UpdatePasswordRequest,
)
from config import DEV_USER_EMAIL, DEV_USER_ID, get_soft_ink_url

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


@router.post("/signup", response_model=SignupResponse, status_code=201)
def signup(body: SignupRequest) -> SignupResponse:
    email = body.email.strip().lower()
    password = body.password
    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required.",
        )
    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters.",
        )
    if demo_mode():
        return SignupResponse(
            needs_confirmation=False,
            access_token=DEV_TOKEN,
            refresh_token=None,
            user=AuthUser(
                id=str(DEV_USER_ID),
                email=email or str(DEV_USER_EMAIL),
                dev=True,
            ),
            message=f"Account created. You are signed in as {email or DEV_USER_EMAIL}.",
        )
    try:
        client = auth_client()
        result = client.auth.sign_up({"email": email, "password": password})
    except HTTPException:
        raise
    except Exception as exc:
        LOG.info("signup failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create account. Try a different email.",
        ) from exc

    session = getattr(result, "session", None) or (
        result.get("session") if isinstance(result, dict) else None
    )
    user = getattr(result, "user", None) or (
        result.get("user") if isinstance(result, dict) else None
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create account. Try a different email.",
        )
    if session is None:
        user_id = (
            str(user.get("id") or "")
            if isinstance(user, dict)
            else str(getattr(user, "id", "") or "")
        )
        return SignupResponse(
            needs_confirmation=True,
            access_token=None,
            refresh_token=None,
            user=AuthUser(id=user_id or "pending", email=email, dev=False),
            message="Account created. Check your email to confirm, then sign in.",
        )
    payload = _session_payload(session, user)
    return SignupResponse(
        needs_confirmation=False,
        access_token=payload.access_token,
        refresh_token=payload.refresh_token,
        user=payload.user,
        message=f"Account created. You are signed in as {payload.user.email or email}.",
    )


@router.get("/me", response_model=MeResponse)
def me(user: Annotated[dict | None, Depends(optional_user)]) -> MeResponse:
    if user is None:
        return MeResponse(authenticated=False, user=None)
    return MeResponse(authenticated=True, user=AuthUser(**user))


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(body: ForgotPasswordRequest) -> ForgotPasswordResponse:
    """Send Supabase recovery email. Always returns ok (no email enumeration)."""
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid email is required.",
        )
    message = (
        "If an account exists for that email, a reset link is on the way. "
        "Check your inbox and spam folder."
    )
    if demo_mode():
        return ForgotPasswordResponse(ok=True, message=message)

    redirect = (body.redirect_to or "").strip()
    if not redirect:
        base = get_soft_ink_url().rstrip("/")
        redirect = f"{base}/auth/reset" if base else ""

    try:
        client = auth_client()
        options = {"redirect_to": redirect} if redirect else None
        client.auth.reset_password_for_email(email, options)
    except HTTPException:
        raise
    except Exception as exc:
        LOG.info("forgot-password failed: %s", exc)
        # Still opaque to the client.
    return ForgotPasswordResponse(ok=True, message=message)


@router.post("/update-password", response_model=ForgotPasswordResponse)
def update_password(
    body: UpdatePasswordRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ForgotPasswordResponse:
    """Set a new password using a recovery (or active) Bearer access token."""
    password = body.password
    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters.",
        )
    if demo_mode():
        return ForgotPasswordResponse(
            ok=True,
            message="Password updated (demo). You can sign in with the new password.",
        )

    scheme, _, token = (authorization or "").partition(" ")
    access = token.strip() if scheme.lower() == "bearer" else ""
    if not access:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Recovery session required. Open the link from your email again.",
        )

    refresh = (body.refresh_token or "").strip() or access
    try:
        client = auth_client()
        client.auth.set_session(access, refresh)
        client.auth.update_user({"password": password})
    except HTTPException:
        raise
    except Exception as exc:
        LOG.info("update-password failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not update password. Request a new reset link.",
        ) from exc
    return ForgotPasswordResponse(
        ok=True,
        message="Password updated. You can sign in with the new password.",
    )


@router.post("/logout")
def logout(_user: Annotated[dict, Depends(require_user)]) -> dict[str, bool]:
    # Client drops the Bearer token; optional server-side revoke later.
    return {"ok": True}

"""Supabase Auth helpers for Streamlit (email + password).

Session tokens live in st.session_state and are mirrored to browser cookies so a
refresh keeps the user signed in until they click Log out.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import streamlit as st
from supabase import Client, create_client

from config import get_supabase_auth_credentials, normalize_supabase_url

LOG = logging.getLogger("tcg.auth")

SESSION_USER_KEY = "auth_user"
SESSION_ACCESS_KEY = "auth_access_token"
SESSION_REFRESH_KEY = "auth_refresh_token"

# Browser cookies (survive Streamlit session_state wipe on refresh).
COOKIE_REFRESH = "tcg_sb_rt"
COOKIE_ACCESS = "tcg_sb_at"
COOKIE_EMAIL = "tcg_sb_em"
COOKIE_USER_ID = "tcg_sb_uid"

_PENDING_SAVE = "_auth_cookie_save"
_PENDING_CLEAR = "_auth_cookie_clear"
_RESTORE_ATTEMPTED = "_auth_cookie_restore_attempted"


def _auth_client() -> Client:
    url, key = get_supabase_auth_credentials()
    if not url or not key:
        raise RuntimeError(
            "Supabase auth credentials missing. Set SUPABASE_URL and "
            "SUPABASE_ANON_KEY (Project Settings → API → anon public). "
            "Do not use the service_role key for login."
        )
    return create_client(normalize_supabase_url(url), key)


def _cookie_manager():
    """Hidden Streamlit component that can read/write document cookies.

    Streamlit forbids two widgets with the same key in one script run, so we
    mount CookieManager at most once per run and reuse that instance.
    """
    import extra_streamlit_components as stx

    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        ctx = get_script_run_ctx()
        run_id = id(ctx) if ctx is not None else None
    except Exception:
        run_id = None

    cached = st.session_state.get("_tcg_auth_cm")
    if cached is not None and st.session_state.get("_tcg_auth_cm_run_id") == run_id:
        return cached

    cm = stx.CookieManager(key="tcg_auth_cookies")
    st.session_state["_tcg_auth_cm"] = cm
    st.session_state["_tcg_auth_cm_run_id"] = run_id
    return cm


def current_user() -> dict[str, Any] | None:
    user = st.session_state.get(SESSION_USER_KEY)
    return user if isinstance(user, dict) else None


def is_authenticated() -> bool:
    return current_user() is not None


def ensure_dev_session() -> None:
    """Inject a stable local user when AUTH_DISABLED is on (no JWT)."""
    from config import DEV_USER_EMAIL, DEV_USER_ID, auth_disabled

    if not auth_disabled():
        return
    existing = current_user()
    if existing and existing.get("id"):
        return
    st.session_state[SESSION_USER_KEY] = {
        "id": str(DEV_USER_ID),
        "email": str(DEV_USER_EMAIL),
        "dev": True,
    }


def _session_tokens(session: Any | None) -> tuple[str, str]:
    if session is None:
        return "", ""
    if isinstance(session, dict):
        access = str(session.get("access_token") or "").strip()
        refresh = str(session.get("refresh_token") or "").strip()
        return access, refresh
    access = str(getattr(session, "access_token", "") or "").strip()
    refresh = str(getattr(session, "refresh_token", "") or "").strip()
    return access, refresh


def _store_session(user: Any, session: Any | None = None) -> None:
    payload = {
        "id": str(getattr(user, "id", "") or ""),
        "email": str(getattr(user, "email", "") or ""),
    }
    if isinstance(user, dict):
        payload["id"] = str(user.get("id") or payload["id"])
        payload["email"] = str(user.get("email") or payload["email"])
    st.session_state[SESSION_USER_KEY] = payload
    access, refresh = _session_tokens(session)
    if access:
        st.session_state[SESSION_ACCESS_KEY] = access
    if refresh:
        st.session_state[SESSION_REFRESH_KEY] = refresh
    st.session_state[_PENDING_SAVE] = True
    st.session_state.pop(_PENDING_CLEAR, None)


def has_jwt_tokens() -> bool:
    return bool(str(st.session_state.get(SESSION_ACCESS_KEY) or "").strip())


def clear_session() -> None:
    for key in (SESSION_USER_KEY, SESSION_ACCESS_KEY, SESSION_REFRESH_KEY):
        st.session_state.pop(key, None)
    st.session_state[_PENDING_CLEAR] = True
    st.session_state.pop(_PENDING_SAVE, None)
    st.session_state.pop(_RESTORE_ATTEMPTED, None)


def _flush_cookie_ops(cm: Any) -> None:
    """Apply pending cookie save/clear after CookieManager is mounted."""
    if st.session_state.pop(_PENDING_CLEAR, False):
        for name in (COOKIE_REFRESH, COOKIE_ACCESS, COOKIE_EMAIL, COOKIE_USER_ID):
            try:
                cm.delete(name)
            except Exception as exc:
                LOG.warning("cookie delete %s failed: %s", name, exc)
        return

    if not st.session_state.pop(_PENDING_SAVE, False):
        return

    access = str(st.session_state.get(SESSION_ACCESS_KEY) or "").strip()
    refresh = str(st.session_state.get(SESSION_REFRESH_KEY) or "").strip()
    user = current_user() or {}
    expires = datetime.now(timezone.utc) + timedelta(days=30)
    try:
        if refresh:
            cm.set(
                COOKIE_REFRESH,
                refresh,
                expires_at=expires,
                same_site="lax",
            )
        if access:
            cm.set(
                COOKIE_ACCESS,
                access,
                expires_at=expires,
                same_site="lax",
            )
        if user.get("email"):
            cm.set(
                COOKIE_EMAIL,
                str(user["email"]),
                expires_at=expires,
                same_site="lax",
            )
        if user.get("id"):
            cm.set(
                COOKIE_USER_ID,
                str(user["id"]),
                expires_at=expires,
                same_site="lax",
            )
    except Exception as exc:
        LOG.warning("cookie save failed: %s", exc)


def _restore_from_cookies(cm: Any) -> bool:
    """Rebuild session_state from cookies after a browser refresh."""
    if st.session_state.get(_RESTORE_ATTEMPTED):
        return is_authenticated() and has_jwt_tokens()
    st.session_state[_RESTORE_ATTEMPTED] = True

    try:
        cookies = cm.get_all()
    except Exception as exc:
        LOG.warning("cookie get_all failed: %s", exc)
        return False
    if cookies is None:
        # Component not ready yet — allow another attempt next run.
        st.session_state.pop(_RESTORE_ATTEMPTED, None)
        return False

    refresh = str(cookies.get(COOKIE_REFRESH) or "").strip()
    access = str(cookies.get(COOKIE_ACCESS) or "").strip()
    email = str(cookies.get(COOKIE_EMAIL) or "").strip()
    user_id = str(cookies.get(COOKIE_USER_ID) or "").strip()
    if not refresh and not access:
        return False

    if refresh:
        st.session_state[SESSION_REFRESH_KEY] = refresh
    if access:
        st.session_state[SESSION_ACCESS_KEY] = access

    if refresh_session():
        # refresh_session updates user + tokens; keep cookies in sync if rotated.
        return True

    # Soft restore: access token still present, user metadata from cookies.
    if access and (user_id or email):
        st.session_state[SESSION_USER_KEY] = {"id": user_id, "email": email}
        try:
            client = _auth_client()
            user = client.auth.get_user(access)
            u = getattr(user, "user", None) or getattr(user, "data", None)
            if u is not None:
                st.session_state[SESSION_USER_KEY] = {
                    "id": str(getattr(u, "id", "") or user_id),
                    "email": str(getattr(u, "email", "") or email),
                }
                return True
        except Exception as exc:
            LOG.warning("get_user from cookie access failed: %s", exc)

    clear_session()
    return False


def bootstrap_auth() -> None:
    """Mount cookie bridge + restore session after refresh. Call once per run."""
    from config import auth_disabled

    if auth_disabled():
        ensure_dev_session()
        return

    cm = _cookie_manager()
    _flush_cookie_ops(cm)

    if is_authenticated() and has_jwt_tokens():
        return

    if _restore_from_cookies(cm):
        _flush_cookie_ops(cm)


def refresh_session() -> bool:
    """Refresh access token when possible. Returns True if session is usable."""
    refresh = str(st.session_state.get(SESSION_REFRESH_KEY) or "").strip()
    if not refresh:
        return bool(st.session_state.get(SESSION_ACCESS_KEY))
    try:
        client = _auth_client()
        response = client.auth.refresh_session(refresh)
        user = getattr(response, "user", None)
        session = getattr(response, "session", None)
        if user is None or session is None:
            return bool(st.session_state.get(SESSION_ACCESS_KEY))
        _store_session(user, session)
        return True
    except Exception as exc:
        LOG.warning("refresh_session failed: %s", exc)
        return bool(st.session_state.get(SESSION_ACCESS_KEY))


def sign_in(email: str, password: str) -> dict[str, Any]:
    email_clean = (email or "").strip().lower()
    if not email_clean or not password:
        raise ValueError("Email and password are required.")
    client = _auth_client()
    response = client.auth.sign_in_with_password(
        {"email": email_clean, "password": password}
    )
    user = getattr(response, "user", None)
    session = getattr(response, "session", None)
    if user is None:
        raise RuntimeError("Sign-in failed. Check email/password.")
    _store_session(user, session)
    if not has_jwt_tokens():
        clear_session()
        raise RuntimeError(
            "Sign-in returned no access token. Check SUPABASE_ANON_KEY "
            "(Project Settings → API → anon public) and try again."
        )
    return current_user() or {}


def sign_up(email: str, password: str) -> dict[str, Any]:
    email_clean = (email or "").strip().lower()
    if not email_clean or not password:
        raise ValueError("Email and password are required.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    client = _auth_client()
    response = client.auth.sign_up({"email": email_clean, "password": password})
    user = getattr(response, "user", None)
    session = getattr(response, "session", None)
    if user is None:
        raise RuntimeError("Sign-up failed. Try a different email.")
    # When email confirmation is ON, session may be None until the user confirms.
    if session is None:
        return {
            "id": str(getattr(user, "id", "") or ""),
            "email": email_clean,
            "needs_confirmation": True,
        }
    _store_session(user, session)
    return current_user() or {}


def sign_out() -> None:
    try:
        client = _auth_client()
        client.auth.sign_out()
    except Exception as exc:
        LOG.warning("sign_out failed: %s", exc)
    clear_session()

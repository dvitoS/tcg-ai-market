"""Supabase Auth helpers for Streamlit (email + password)."""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st
from supabase import Client, create_client

from config import get_supabase_auth_credentials, normalize_supabase_url

LOG = logging.getLogger("tcg.auth")

SESSION_USER_KEY = "auth_user"
SESSION_ACCESS_KEY = "auth_access_token"
SESSION_REFRESH_KEY = "auth_refresh_token"


def _auth_client() -> Client:
    url, key = get_supabase_auth_credentials()
    if not url or not key:
        raise RuntimeError(
            "Supabase auth credentials missing. Set SUPABASE_URL and "
            "SUPABASE_ANON_KEY (preferred) or SUPABASE_KEY."
        )
    return create_client(normalize_supabase_url(url), key)


def current_user() -> dict[str, Any] | None:
    user = st.session_state.get(SESSION_USER_KEY)
    return user if isinstance(user, dict) else None


def is_authenticated() -> bool:
    return current_user() is not None


def _store_session(user: Any, session: Any | None = None) -> None:
    payload = {
        "id": str(getattr(user, "id", "") or ""),
        "email": str(getattr(user, "email", "") or ""),
    }
    st.session_state[SESSION_USER_KEY] = payload
    if session is not None:
        access = getattr(session, "access_token", None)
        refresh = getattr(session, "refresh_token", None)
        if access:
            st.session_state[SESSION_ACCESS_KEY] = access
        if refresh:
            st.session_state[SESSION_REFRESH_KEY] = refresh


def clear_session() -> None:
    for key in (SESSION_USER_KEY, SESSION_ACCESS_KEY, SESSION_REFRESH_KEY):
        st.session_state.pop(key, None)


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

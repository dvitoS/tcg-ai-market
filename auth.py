"""Supabase Auth helpers for Streamlit (email + password).

Streamlit wipes st.session_state on browser refresh. CookieManager is unreliable
inside Streamlit's sandboxed iframes, so we persist an opaque session id:

  1. On login → save tokens under .data/auth_sessions/<sid>.json
  2. Put sid in st.query_params (survives refresh) + session_state
  3. On bootstrap → load sid from query/session and restore tokens
  4. On logout → delete file + clear sid from URL
"""

from __future__ import annotations

import json
import logging
import secrets
import time
from pathlib import Path
from typing import Any

import streamlit as st
from supabase import Client, create_client

from config import PROJECT_ROOT, get_supabase_auth_credentials, normalize_supabase_url

LOG = logging.getLogger("tcg.auth")

SESSION_USER_KEY = "auth_user"
SESSION_ACCESS_KEY = "auth_access_token"
SESSION_REFRESH_KEY = "auth_refresh_token"
SESSION_SID_KEY = "auth_sid"

QUERY_SID = "sid"
SESSIONS_DIR = PROJECT_ROOT / ".data" / "auth_sessions"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


def _auth_client() -> Client:
    url, key = get_supabase_auth_credentials()
    if not url or not key:
        raise RuntimeError(
            "Supabase auth credentials missing. Set SUPABASE_URL and "
            "SUPABASE_ANON_KEY (Project Settings → API → anon public). "
            "Do not use the service_role key for login."
        )
    return create_client(normalize_supabase_url(url), key)


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


def has_jwt_tokens() -> bool:
    return bool(str(st.session_state.get(SESSION_ACCESS_KEY) or "").strip())


def _sessions_dir() -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def _session_path(sid: str) -> Path:
    safe = "".join(ch for ch in sid if ch.isalnum() or ch in {"-", "_"})
    if not safe or safe != sid:
        raise ValueError("Invalid session id")
    return _sessions_dir() / f"{safe}.json"


def _write_server_session(sid: str, *, user: dict[str, Any], access: str, refresh: str) -> None:
    payload = {
        "user": {"id": str(user.get("id") or ""), "email": str(user.get("email") or "")},
        "access_token": access,
        "refresh_token": refresh,
        "updated_at": int(time.time()),
    }
    path = _session_path(sid)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_server_session(sid: str) -> dict[str, Any] | None:
    try:
        path = _session_path(sid)
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        LOG.warning("read session %s failed: %s", sid[:8], exc)
        return None
    if not isinstance(data, dict):
        return None
    updated = int(data.get("updated_at") or 0)
    if updated and (time.time() - updated) > SESSION_TTL_SECONDS:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        return None
    return data


def _delete_server_session(sid: str) -> None:
    try:
        _session_path(sid).unlink(missing_ok=True)
    except Exception as exc:
        LOG.warning("delete session failed: %s", exc)


def _get_sid() -> str:
    sid = str(st.session_state.get(SESSION_SID_KEY) or "").strip()
    if sid:
        return sid
    try:
        sid = str(st.query_params.get(QUERY_SID) or "").strip()
    except Exception:
        sid = ""
    return sid


def _bind_sid(sid: str) -> None:
    st.session_state[SESSION_SID_KEY] = sid
    try:
        st.query_params[QUERY_SID] = sid
    except Exception as exc:
        LOG.warning("set query sid failed: %s", exc)


def _clear_sid() -> None:
    st.session_state.pop(SESSION_SID_KEY, None)
    try:
        if QUERY_SID in st.query_params:
            del st.query_params[QUERY_SID]
    except Exception:
        try:
            params = dict(st.query_params)
            params.pop(QUERY_SID, None)
            st.query_params.from_dict(params)
        except Exception as exc:
            LOG.warning("clear query sid failed: %s", exc)


def _persist_current_session() -> None:
    """Write tokens to disk and keep sid in the URL."""
    user = current_user() or {}
    access = str(st.session_state.get(SESSION_ACCESS_KEY) or "").strip()
    refresh = str(st.session_state.get(SESSION_REFRESH_KEY) or "").strip()
    if not user.get("id") or not (access or refresh):
        return
    sid = _get_sid() or secrets.token_urlsafe(24)
    _write_server_session(sid, user=user, access=access, refresh=refresh)
    _bind_sid(sid)


def _apply_server_payload(data: dict[str, Any]) -> bool:
    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    access = str(data.get("access_token") or "").strip()
    refresh = str(data.get("refresh_token") or "").strip()
    if not refresh and not access:
        return False
    st.session_state[SESSION_USER_KEY] = {
        "id": str(user.get("id") or ""),
        "email": str(user.get("email") or ""),
    }
    if access:
        st.session_state[SESSION_ACCESS_KEY] = access
    if refresh:
        st.session_state[SESSION_REFRESH_KEY] = refresh
    return True


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
    _persist_current_session()


def clear_session() -> None:
    sid = _get_sid()
    if sid:
        _delete_server_session(sid)
    for key in (SESSION_USER_KEY, SESSION_ACCESS_KEY, SESSION_REFRESH_KEY, SESSION_SID_KEY):
        st.session_state.pop(key, None)
    _clear_sid()


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


def _restore_from_server() -> bool:
    sid = _get_sid()
    if not sid:
        return False
    data = _read_server_session(sid)
    if not data:
        _clear_sid()
        return False
    if not _apply_server_payload(data):
        return False
    _bind_sid(sid)
    if has_jwt_tokens():
        # Best-effort rotate tokens; keep existing if refresh fails.
        refresh_session()
        return has_jwt_tokens() or bool(st.session_state.get(SESSION_REFRESH_KEY))
    if refresh_session() and has_jwt_tokens():
        return True
    return False


def bootstrap_auth() -> None:
    """Restore durable session after refresh. Call once per run near the top."""
    from config import auth_disabled

    if auth_disabled():
        ensure_dev_session()
        return

    if is_authenticated() and has_jwt_tokens():
        # Keep server copy fresh while the tab stays open.
        _persist_current_session()
        return

    _restore_from_server()


def persist_cookies_now() -> None:
    """Back-compat no-op name — durable session is written in _store_session."""
    _persist_current_session()


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

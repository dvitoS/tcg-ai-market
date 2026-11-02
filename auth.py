"""Supabase Auth helpers for Streamlit (email + password).

Streamlit wipes st.session_state on browser refresh. We persist an opaque
session id in the URL (?sid=) and store JWT material in Supabase table
`auth_sessions` (service_role only) so Streamlit Cloud / multi-instance works.

Local `.data/auth_sessions/` is allowed only off Cloud (single-process dev).
"""

from __future__ import annotations

import json
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
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
AUTH_SESSIONS_TABLE = "auth_sessions"


def _auth_client() -> Client:
    url, key = get_supabase_auth_credentials()
    if not url or not key:
        raise RuntimeError(
            "Supabase auth credentials missing. Set SUPABASE_URL and "
            "SUPABASE_ANON_KEY (Project Settings → API → anon public). "
            "Do not use the service_role key for login."
        )
    return create_client(normalize_supabase_url(url), key)


def _service_client() -> Client | None:
    """Service-role client for auth_sessions (never use for portfolio RLS)."""
    try:
        from database import get_supabase

        return get_supabase()
    except Exception as exc:
        LOG.warning("service client unavailable: %s", exc)
        return None


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


def _safe_sid(sid: str) -> str:
    safe = "".join(ch for ch in sid if ch.isalnum() or ch in {"-", "_"})
    if not safe or safe != sid:
        raise ValueError("Invalid session id")
    return safe


def _allow_local_session_fallback() -> bool:
    """Disk sessions are not durable across Streamlit Cloud workers."""
    from config import _is_streamlit_cloud

    return not _is_streamlit_cloud()


def _sessions_dir() -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def _session_path(sid: str) -> Path:
    return _sessions_dir() / f"{_safe_sid(sid)}.json"


def _write_local_session(sid: str, *, user: dict[str, Any], access: str, refresh: str) -> None:
    payload = {
        "user": {"id": str(user.get("id") or ""), "email": str(user.get("email") or "")},
        "access_token": access,
        "refresh_token": refresh,
        "updated_at": int(time.time()),
    }
    _session_path(sid).write_text(json.dumps(payload), encoding="utf-8")


def _read_local_session(sid: str) -> dict[str, Any] | None:
    try:
        path = _session_path(sid)
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        LOG.warning("read local session failed: %s", exc)
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


def _delete_local_session(sid: str) -> None:
    try:
        _session_path(sid).unlink(missing_ok=True)
    except Exception as exc:
        LOG.warning("delete local session failed: %s", exc)


def _write_supabase_session(
    sid: str, *, user: dict[str, Any], access: str, refresh: str
) -> bool:
    client = _service_client()
    if client is None:
        return False
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=SESSION_TTL_SECONDS)
    row = {
        "sid": _safe_sid(sid),
        "user_id": str(user.get("id") or "") or None,
        "email": str(user.get("email") or "") or None,
        "access_token": access or None,
        "refresh_token": refresh or None,
        "updated_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }
    try:
        client.table(AUTH_SESSIONS_TABLE).upsert(row, on_conflict="sid").execute()
        return True
    except Exception as exc:
        LOG.warning("supabase auth_sessions upsert failed: %s", exc)
        return False


def _read_supabase_session(sid: str) -> dict[str, Any] | None:
    client = _service_client()
    if client is None:
        return None
    try:
        response = (
            client.table(AUTH_SESSIONS_TABLE)
            .select("sid,user_id,email,access_token,refresh_token,updated_at,expires_at")
            .eq("sid", _safe_sid(sid))
            .limit(1)
            .execute()
        )
    except Exception as exc:
        LOG.warning("supabase auth_sessions read failed: %s", exc)
        return None
    rows = list(response.data or [])
    if not rows:
        return None
    row = rows[0]
    expires_raw = row.get("expires_at")
    if expires_raw:
        try:
            expires_at = datetime.fromisoformat(str(expires_raw).replace("Z", "+00:00"))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                _delete_supabase_session(sid)
                return None
        except Exception:
            pass
    return {
        "user": {
            "id": str(row.get("user_id") or ""),
            "email": str(row.get("email") or ""),
        },
        "access_token": str(row.get("access_token") or ""),
        "refresh_token": str(row.get("refresh_token") or ""),
    }


def _delete_supabase_session(sid: str) -> None:
    client = _service_client()
    if client is None:
        return
    try:
        client.table(AUTH_SESSIONS_TABLE).delete().eq("sid", _safe_sid(sid)).execute()
    except Exception as exc:
        LOG.warning("supabase auth_sessions delete failed: %s", exc)


def _write_server_session(sid: str, *, user: dict[str, Any], access: str, refresh: str) -> None:
    if _write_supabase_session(sid, user=user, access=access, refresh=refresh):
        if _allow_local_session_fallback():
            # Local mirror for faster single-process restarts; ignore failures.
            try:
                _write_local_session(sid, user=user, access=access, refresh=refresh)
            except Exception:
                pass
        return
    if _allow_local_session_fallback():
        _write_local_session(sid, user=user, access=access, refresh=refresh)
        return
    raise RuntimeError(
        "Could not persist auth session to Supabase auth_sessions. "
        "Run supabase_auth_sessions.sql and check the service_role key."
    )


def _read_server_session(sid: str) -> dict[str, Any] | None:
    data = _read_supabase_session(sid)
    if data is not None:
        return data
    if _allow_local_session_fallback():
        return _read_local_session(sid)
    return None


def _delete_server_session(sid: str) -> None:
    _delete_supabase_session(sid)
    if _allow_local_session_fallback():
        _delete_local_session(sid)


def purge_expired_auth_sessions() -> int:
    """Delete expired auth_sessions rows (service_role). Returns deleted count guess."""
    client = _service_client()
    if client is None:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    try:
        response = (
            client.table(AUTH_SESSIONS_TABLE)
            .delete()
            .lt("expires_at", now)
            .execute()
        )
        rows = list(response.data or [])
        deleted = len(rows)
        if deleted:
            LOG.info("Purged %s expired auth_sessions", deleted)
        return deleted
    except Exception as exc:
        LOG.warning("purge_expired_auth_sessions failed: %s", exc)
        return 0


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
    """Write tokens to Supabase (or local fallback) and keep sid in the URL."""
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
        _persist_current_session()
        return

    _restore_from_server()


def persist_cookies_now() -> None:
    """Back-compat name — durable session is written in _store_session."""
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

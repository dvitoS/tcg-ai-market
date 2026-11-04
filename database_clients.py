"""Supabase client helpers (service vs JWT user)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from config import _secret, get_supabase_credentials

if TYPE_CHECKING:
    from supabase import Client

PAGE = 1000

# FastAPI (and other non-Streamlit) callers bind the Bearer access token here
# so portfolio/watchlist RLS uses the same JWT that authenticated the request.
_request_access_token: ContextVar[str | None] = ContextVar(
    "kestrel_request_access_token", default=None
)


def set_request_access_token(token: str | None) -> Token:
    """Bind a user JWT for the current request/task. Return token for reset()."""
    cleaned = str(token or "").strip() or None
    return _request_access_token.set(cleaned)


def reset_request_access_token(token: Token) -> None:
    _request_access_token.reset(token)


def get_request_access_token() -> str | None:
    return _request_access_token.get()

def _supabase_api():
    """Lazy import — keeps module load working if supabase wheels are mid-install."""
    try:
        from supabase import Client, create_client
    except ImportError as exc:
        raise ImportError(
            "supabase package missing or broken. "
            "Add 'supabase' to requirements.txt and reboot the Cloud app."
        ) from exc
    return Client, create_client


@dataclass
class Card:
    id: str
    name: str | None = None
    supertype: str | None = None
    rarity: str | None = None
    set_name: str | None = None
    market_price: float | None = None
    pokewallet_id: str | None = None
    tcgplayer_id: str | None = None
    image_url: str | None = None


def _require_supabase_env() -> tuple[str, str]:
    url, key = get_supabase_credentials()
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY are not set. "
            "Add them in Streamlit Secrets (Cloud) or .env (local)."
        )
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        raise RuntimeError(
            "SUPABASE_URL must be the Project URL (https://xxxx.supabase.co), "
            "not a Postgres connection string. Put the Postgres URI in SUPABASE_DB_URL."
        )
    if "supabase.co" not in url and "localhost" not in url:
        raise RuntimeError(
            f"Suspicious SUPABASE_URL: {url!r}. "
            "Expected e.g. https://YOUR_PROJECT.supabase.co "
            "(without /rest/v1 at the end)."
        )
    return url, key


@lru_cache(maxsize=1)
def get_supabase():
    """Service-role (or configured key) client — catalog/history/sync."""
    _, create_client = _supabase_api()
    url, key = _require_supabase_env()
    return create_client(url, key)


_JWT_FAIL_KEY = "_user_supabase_fail_reason"


def jwt_role_claim(key: str) -> str | None:
    """Best-effort decode of Supabase JWT ``role`` without verifying signature."""
    import base64
    import json

    raw = str(key or "").strip()
    parts = raw.split(".")
    if len(parts) < 2:
        return None
    try:
        pad = "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
        role = payload.get("role")
        return str(role) if role else None
    except Exception:
        return None


def last_user_supabase_error() -> str:
    try:
        import streamlit as st

        return str(st.session_state.get(_JWT_FAIL_KEY) or "").strip()
    except Exception:
        return ""


def _anon_credentials_ok() -> tuple[str, str] | None:
    """Return (url, anon_key) when usable for user JWT clients; else None."""
    from config import _clean_secret_value, get_supabase_auth_credentials

    url, anon = get_supabase_auth_credentials()
    has_anon = bool(_clean_secret_value(_secret("SUPABASE_ANON_KEY")))
    if not url or not anon or not has_anon:
        return None
    if jwt_role_claim(anon) == "service_role":
        return None
    return url, anon


def _client_for_access_token(access: str):
    """Anon + user JWT client for PostgREST RLS (FastAPI Bearer or Streamlit session)."""
    creds = _anon_credentials_ok()
    if creds is None:
        return None
    url, anon = creds
    access = str(access or "").strip()
    if not access:
        return None
    try:
        _, create_client = _supabase_api()
        client = create_client(url, anon)
        # PostgREST Authorization — enough for portfolio/watchlist table ops.
        try:
            client.postgrest.auth(access)
        except Exception:
            # Older clients: set_session still stamps the JWT on requests.
            client.auth.set_session(access, access)
        return client
    except Exception as exc:
        import logging

        logging.getLogger("tcg.database").warning(
            "Bearer user supabase client failed: %s", exc
        )
        return None


def get_user_supabase():
    """Authed anon client with the signed-in user's JWT (portfolio/watchlist RLS).

    Prefer FastAPI request Bearer (ContextVar), then Streamlit session tokens.
    Returns None when anon key or session tokens are missing.
    Production callers must NOT fall back to service_role for user tables.
    """
    # Soft Ink / FastAPI: Authorization Bearer bound for this request.
    request_token = get_request_access_token()
    if request_token:
        client = _client_for_access_token(request_token)
        if client is not None:
            return client
        return None

    try:
        import streamlit as st

        from auth import SESSION_ACCESS_KEY, SESSION_REFRESH_KEY, refresh_session
    except Exception:
        return None

    if _anon_credentials_ok() is None:
        role = None
        try:
            from config import get_supabase_auth_credentials

            _, anon = get_supabase_auth_credentials()
            role = jwt_role_claim(anon)
        except Exception:
            role = None
        if role == "service_role":
            try:
                st.session_state[_JWT_FAIL_KEY] = (
                    "SUPABASE_ANON_KEY looks like service_role — use the anon public key."
                )
            except Exception:
                pass
        return None

    refresh_session()
    access = str(st.session_state.get(SESSION_ACCESS_KEY) or "").strip()
    refresh = str(st.session_state.get(SESSION_REFRESH_KEY) or "").strip()
    if not access:
        return None
    try:
        from config import get_supabase_auth_credentials

        url, anon = get_supabase_auth_credentials()
        _, create_client = _supabase_api()
        client = create_client(url, anon)
        # Prefer real refresh token; access-as-refresh is a last resort for legacy sessions.
        client.auth.set_session(access, refresh or access)
        try:
            # Touch auth so a bad token fails here instead of later on PostgREST.
            client.auth.get_user(access)
        except TypeError:
            client.auth.get_user()
        except Exception as user_exc:
            # set_session may still be enough for PostgREST; keep client if session exists.
            session = client.auth.get_session()
            if session is None:
                raise user_exc
        try:
            st.session_state.pop(_JWT_FAIL_KEY, None)
        except Exception:
            pass
        return client
    except Exception as exc:
        import logging

        logging.getLogger("tcg.database").warning("get_user_supabase failed: %s", exc)
        try:
            st.session_state[_JWT_FAIL_KEY] = str(exc)[:180]
        except Exception:
            pass
        return None


def _user_data_client():
    """Client for portfolio/watchlist.

    - Prefer JWT (anon key + user session / Bearer) so RLS enforces auth.uid().
    - Service-role allowed only when AUTH_DISABLED (local single-user).
    """
    from config import auth_disabled

    user_client = get_user_supabase()
    if user_client is not None:
        return user_client
    if auth_disabled():
        return get_supabase()
    raise RuntimeError(
        "Portfolio/watchlist need a JWT session (SUPABASE_ANON_KEY + login). "
        "Service role is not used for user data in multi-user mode."
    )


# Back-compat alias — old name implied a silent service fallback.
def _user_or_service_client():
    return _user_data_client()


def user_data_client_mode() -> str:
    """jwt | missing_anon | missing_token | jwt_failed | dev_service | anonymous."""
    try:
        import auth as auth_mod
        from config import _clean_secret_value, auth_disabled
    except Exception:
        return "anonymous"
    # FastAPI Soft Ink request with Bearer already bound.
    if get_request_access_token():
        has_anon = bool(_clean_secret_value(_secret("SUPABASE_ANON_KEY")))
        if not has_anon:
            return "missing_anon"
        if get_user_supabase() is not None:
            return "jwt"
        return "jwt_failed"
    if not auth_mod.is_authenticated():
        return "anonymous"
    if auth_disabled() and not auth_mod.has_jwt_tokens():
        return "dev_service"
    has_anon = bool(_clean_secret_value(_secret("SUPABASE_ANON_KEY")))
    if not has_anon:
        return "missing_anon"
    if not auth_mod.has_jwt_tokens():
        return "missing_token"
    if get_user_supabase() is not None:
        return "jwt"
    return "jwt_failed"


def _chunked(rows: list[dict[str, Any]], size: int = 500):
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _as_iso_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _card_from_row(row: dict[str, Any]) -> Card:
    price = row.get("market_price")
    return Card(
        id=str(row["id"]),
        name=row.get("name"),
        supertype=row.get("supertype"),
        rarity=row.get("rarity"),
        set_name=row.get("set_name"),
        market_price=float(price) if price is not None else None,
        pokewallet_id=row.get("pokewallet_id"),
        tcgplayer_id=row.get("tcgplayer_id"),
        image_url=row.get("image_url"),
    )


def fetch_all(table: str, columns: str = "*", *, order: str | None = None) -> list[dict[str, Any]]:
    """Straničenje — PostgREST default max ~1000 redova po zahtjevu."""
    client = get_supabase()
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        query = client.table(table).select(columns)
        if order:
            query = query.order(order)
        response = query.range(start, start + PAGE - 1).execute()
        batch = list(response.data or [])
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        start += PAGE
    return rows


def table_count(table: str) -> int:
    client = get_supabase()
    response = client.table(table).select("*", count="exact").limit(1).execute()
    return int(response.count or 0)

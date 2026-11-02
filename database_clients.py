"""Supabase client helpers (service vs JWT user)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from config import _secret, get_supabase_credentials

if TYPE_CHECKING:
    from supabase import Client

PAGE = 1000

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


def get_user_supabase():
    """Authed anon client with the signed-in user's JWT (portfolio/watchlist RLS).

    Returns None when anon key or session tokens are missing.
    Production callers must NOT fall back to service_role for user tables.
    """
    try:
        import streamlit as st

        from auth import SESSION_ACCESS_KEY, SESSION_REFRESH_KEY, refresh_session
        from config import _clean_secret_value, get_supabase_auth_credentials
    except Exception:
        return None

    url, anon = get_supabase_auth_credentials()
    has_anon = bool(_clean_secret_value(_secret("SUPABASE_ANON_KEY")))
    if not url or not anon or not has_anon:
        return None
    refresh_session()
    access = str(st.session_state.get(SESSION_ACCESS_KEY) or "").strip()
    refresh = str(st.session_state.get(SESSION_REFRESH_KEY) or "").strip()
    if not access:
        return None
    try:
        _, create_client = _supabase_api()
        client = create_client(url, anon)
        # refresh_token is required by gotrue set_session
        client.auth.set_session(access, refresh or access)
        # Touch auth so a bad token fails here instead of later on PostgREST.
        client.auth.get_user(access)
        return client
    except Exception as exc:
        import logging

        logging.getLogger("tcg.database").warning("get_user_supabase failed: %s", exc)
        return None


def _user_data_client():
    """Client for portfolio/watchlist.

    - Prefer JWT (anon key + user session) so RLS enforces auth.uid().
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

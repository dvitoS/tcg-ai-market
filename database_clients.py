"""Supabase client helpers (service vs JWT user)."""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from config import _secret, get_supabase_credentials

if TYPE_CHECKING:
    from supabase import Client

LOG = logging.getLogger("tcg.database")
PAGE = 1000
T = TypeVar("T")

# Long nightlies reuse one PostgREST httpx client. With HTTP/2 the peer
# (Cloudflare / Supabase) terminates around stream id 19999
# (``RemoteProtocolError: ConnectionTerminated``). Prefer HTTP/1.1 and
# reconnect on that class of transport failure.
_TRANSIENT_TRANSPORT_NAMES = frozenset(
    {
        "RemoteProtocolError",
        "ConnectError",
        "ConnectTimeout",
        "ReadTimeout",
        "WriteTimeout",
        "PoolTimeout",
        "NetworkError",
    }
)

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
    try:
        _request_access_token.reset(token)
    except ValueError:
        # Token was set in another Context (threadpool / nested middleware).
        _request_access_token.set(None)


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
    finishes: str | None = None
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


def _http1_service_options():
    """Build SyncClientOptions with an HTTP/1.1 httpx client when available."""
    try:
        import httpx
        from supabase.lib.client_options import SyncClientOptions
    except ImportError:
        return None
    timeout = httpx.Timeout(120.0)
    return SyncClientOptions(
        httpx_client=httpx.Client(
            http2=False,
            timeout=timeout,
            follow_redirects=True,
        ),
        postgrest_client_timeout=timeout,
    )


def _force_postgrest_http1(client: Any) -> None:
    """Fallback when SyncClientOptions.httpx_client is unavailable."""
    try:
        import httpx
    except ImportError:
        return
    try:
        pg = client.postgrest
        old = getattr(pg, "session", None)
        base = str(getattr(pg, "base_url", "") or "")
        headers = dict(getattr(old, "headers", {}) or {})
        timeout = getattr(old, "timeout", httpx.Timeout(120.0))
        pg.session = httpx.Client(
            base_url=base or None,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
            http2=False,
        )
        if old is not None:
            try:
                old.close()
            except Exception:
                pass
    except Exception as exc:
        LOG.warning("Could not force PostgREST HTTP/1.1: %s", exc)


def _close_supabase_client(client: Any) -> None:
    if client is None:
        return
    try:
        http = getattr(getattr(client, "options", None), "httpx_client", None)
        if http is not None:
            http.close()
            return
    except Exception:
        pass
    try:
        session = getattr(getattr(client, "postgrest", None), "session", None)
        if session is not None:
            session.close()
    except Exception:
        pass


@lru_cache(maxsize=1)
def get_supabase():
    """Service-role (or configured key) client — catalog/history/sync.

    Uses HTTP/1.1 for PostgREST to avoid HTTP/2 stream-id exhaustion on
    multi-hour nightlies (see ConnectionTerminated last_stream_id≈19999).
    """
    _, create_client = _supabase_api()
    url, key = _require_supabase_env()
    options = _http1_service_options()
    if options is not None:
        try:
            return create_client(url, key, options=options)
        except TypeError:
            # Older supabase-py without options= / SyncClientOptions support.
            http = getattr(options, "httpx_client", None)
            if http is not None:
                try:
                    http.close()
                except Exception:
                    pass
    client = create_client(url, key)
    _force_postgrest_http1(client)
    return client


def reset_supabase() -> None:
    """Drop the cached service client so the next call opens a fresh connection."""
    client = None
    try:
        # Peek without creating a new client if cache is empty.
        cache_info = get_supabase.cache_info()
        if cache_info.currsize:
            client = get_supabase()
    except Exception:
        client = None
    get_supabase.cache_clear()
    _close_supabase_client(client)


def is_transient_supabase_transport_error(exc: BaseException) -> bool:
    """True for HTTP/2 terminate / connection blips worth a reconnect retry."""
    name = type(exc).__name__
    if name in _TRANSIENT_TRANSPORT_NAMES:
        return True
    # httpx sometimes wraps httpcore errors; match the wire signature too.
    text = f"{name}: {exc}"
    return "ConnectionTerminated" in text or "RemoteProtocolError" in text


def call_with_supabase_reconnect(
    op: Callable[[], T],
    *,
    retries: int = 2,
    label: str = "supabase",
) -> T:
    """Run ``op``; on transient transport errors reset the client and retry."""
    attempts = max(0, int(retries)) + 1
    last: BaseException | None = None
    for attempt in range(attempts):
        try:
            return op()
        except Exception as exc:
            last = exc
            if attempt + 1 >= attempts or not is_transient_supabase_transport_error(exc):
                raise
            LOG.warning(
                "%s transport error (attempt %s/%s): %s — reconnecting",
                label,
                attempt + 1,
                attempts,
                exc,
            )
            reset_supabase()
            time.sleep(0.4 * (attempt + 1))
    assert last is not None
    raise last


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
    finishes = row.get("finishes")
    return Card(
        id=str(row["id"]),
        name=row.get("name"),
        supertype=row.get("supertype"),
        rarity=row.get("rarity"),
        set_name=row.get("set_name"),
        market_price=float(price) if price is not None else None,
        pokewallet_id=row.get("pokewallet_id"),
        tcgplayer_id=row.get("tcgplayer_id"),
        finishes=str(finishes).strip() if finishes else None,
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


def table_has_rows(table: str) -> bool:
    """Cheap existence probe — never ``COUNT(*)`` (times out on price_history ~2M)."""
    client = get_supabase()
    # Prefer a narrow column when we know the schema.
    column = "card_id" if table == "price_history" else "id" if table == "cards" else "*"
    try:
        response = client.table(table).select(column).limit(1).execute()
        return bool(response.data)
    except Exception:
        if column == "*":
            raise
        response = client.table(table).select("*").limit(1).execute()
        return bool(response.data)


def table_count(table: str) -> int:
    """Row count. Uses estimated counts for huge tables; falls back to presence.

    Exact ``COUNT(*)`` on ``price_history`` (~2M rows) hits Supabase statement
    timeout (57014) and aborted nightly in ``ensure_seed_database``.
    """
    client = get_supabase()
    # PostgREST: exact is expensive; estimated/planned avoid full scans.
    modes = ("estimated", "planned", "exact") if table == "price_history" else ("exact",)
    last_exc: Exception | None = None
    for mode in modes:
        try:
            response = client.table(table).select("*", count=mode).limit(1).execute()
            if response.count is not None:
                return int(response.count)
        except Exception as exc:
            last_exc = exc
            continue
    # Seed / emptiness checks only need >0 — don't fail the whole nightly.
    if table_has_rows(table):
        return 1
    if last_exc is not None:
        raise last_exc
    return 0

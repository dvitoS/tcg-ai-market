"""Multi-source price history for Soft Ink detail (DB + JustTCG NM + PSA 9/10)."""

from __future__ import annotations

import logging
import threading
import time
from datetime import date, timedelta
from typing import Any

from api.catalog_service import load_board, load_card_history
from justtcg_client import JustTCGRateLimitError, justtcg_api_key, normalize_card_number
from services.prices import record_justtcg_event

LOG = logging.getLogger("kestrel.api.price_sources")

# Soft Ink used to live-call JustTCG NM+PSA on every card detail mount.
# Nightly already writes JustTCG NM into price_history — prefer that for NM.
_SOURCES_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_SOURCES_CACHE_LOCK = threading.Lock()
_SOURCES_CACHE_TTL_SECONDS = 45 * 60
_SOURCES_CACHE_EMPTY_TTL_SECONDS = 15 * 60
_SOURCES_CACHE_MAX = 256
_DB_NM_MIN_POINTS = 7
_DB_NM_MAX_AGE_DAYS = 3


def clear_price_sources_cache() -> None:
    with _SOURCES_CACHE_LOCK:
        _SOURCES_CACHE.clear()


def _points_from_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows or []:
        try:
            out.append(
                {
                    "date": str(row.get("date") or "")[:10],
                    "price": float(row["price"]),
                }
            )
        except (TypeError, ValueError, KeyError):
            continue
    out.sort(key=lambda p: p["date"])
    return out


def _market_history_is_fresh(market: list[dict[str, Any]]) -> bool:
    """True when nightly/DB NM series is usable — skip a live JustTCG NM call."""
    if len(market) < _DB_NM_MIN_POINTS:
        return False
    try:
        last = date.fromisoformat(str(market[-1]["date"])[:10])
    except (TypeError, ValueError, KeyError):
        return False
    return last >= date.today() - timedelta(days=_DB_NM_MAX_AGE_DAYS)


def _resolve_tcp_from_board(card_id: str) -> tuple[str, str, str | None]:
    """Return (name, set_name, tcgplayer_id) best-effort from board/DB."""
    name = str(card_id)
    set_name = ""
    tcp: str | None = None
    board, _ = load_board()
    if board is not None and not board.empty:
        hits = board[board["id"].astype(str) == str(card_id)]
        if not hits.empty:
            row = hits.iloc[0]
            name = str(row.get("name") or card_id)
            set_name = str(row.get("set_name") or "")
            raw_tcp = row.get("tcgplayer_id") if hasattr(row, "get") else None
            if raw_tcp is not None and str(raw_tcp).strip() and str(raw_tcp).lower() != "nan":
                tcp = str(raw_tcp).strip()
    if tcp:
        return name, set_name, tcp
    try:
        from database import get_card

        card = get_card(str(card_id))
        if card is not None:
            name = str(card.name or name)
            set_name = str(getattr(card, "set_name", None) or set_name)
            if getattr(card, "tcgplayer_id", None):
                tcp = str(card.tcgplayer_id)
    except Exception as exc:
        LOG.info("get_card tcgplayer_id lookup failed: %s", exc)
    return name, set_name, tcp


def _cache_get(cache_key: str) -> dict[str, Any] | None:
    now = time.monotonic()
    with _SOURCES_CACHE_LOCK:
        hit = _SOURCES_CACHE.get(cache_key)
        if hit is None:
            return None
        expires_at, payload = hit
        if expires_at <= now:
            _SOURCES_CACHE.pop(cache_key, None)
            return None
        return dict(payload)


def _cache_put(cache_key: str, payload: dict[str, Any], *, ttl: float) -> None:
    with _SOURCES_CACHE_LOCK:
        if len(_SOURCES_CACHE) >= _SOURCES_CACHE_MAX and cache_key not in _SOURCES_CACHE:
            oldest = next(iter(_SOURCES_CACHE), None)
            if oldest is not None:
                _SOURCES_CACHE.pop(oldest, None)
        _SOURCES_CACHE[cache_key] = (time.monotonic() + ttl, dict(payload))


def build_card_price_sources(card_id: str, *, limit: int = 180) -> dict[str, Any]:
    card_id = str(card_id).strip()
    limit = max(1, min(int(limit or 180), 365))
    cache_key = f"v2|{card_id}|{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        cached["cache"] = "hit"
        record_justtcg_event("cache_hit")
        return cached

    market = _points_from_rows(load_card_history(card_id, limit=limit))
    name, set_name, tcp = _resolve_tcp_from_board(card_id)
    has_key = bool(justtcg_api_key())
    number = ""
    if "-" in card_id:
        number = normalize_card_number(card_id.rsplit("-", 1)[-1])

    justtcg: list[dict[str, Any]] = []
    justtcg_error: str | None = None
    justtcg_fallback = False
    justtcg_from_db = False
    psa10: list[dict[str, Any]] = []
    psa10_error: str | None = None
    psa10_stats: dict[str, Any] = {}
    psa9: list[dict[str, Any]] = []
    psa9_error: str | None = None
    psa9_stats: dict[str, Any] = {}
    rate_limited = False
    use_db_nm = _market_history_is_fresh(market)
    nm_outcome: str | None = None

    if has_key and use_db_nm:
        # Nightly JustTCG NM sync already populated price_history — don't re-burn quota.
        justtcg = list(market)
        justtcg_from_db = True
        nm_outcome = "db"
        LOG.info("using DB NM history for %s (%s pts) — skip live JustTCG NM", card_id, len(market))
    elif has_key:
        try:
            from justtcg_client import nm_history_for_card

            points, resolved = nm_history_for_card(
                tcgplayer_id=tcp,
                name=name,
                number=number or None,
                set_name=set_name or None,
            )
            if resolved:
                tcp = str(resolved)
            justtcg = _points_from_rows(points)
            if justtcg:
                nm_outcome = "live"
            else:
                nm_outcome = "empty"
        except JustTCGRateLimitError as exc:
            rate_limited = True
            justtcg_error = "JustTCG rate limited — try again later."
            nm_outcome = "error"
            LOG.warning("nm_history_for_card rate-limited for %s", card_id)
            _ = exc
        except Exception as exc:
            justtcg_error = str(exc)[:180]
            nm_outcome = "error"
            LOG.info("nm_history_for_card failed for %s: %s", card_id, exc)

        if not justtcg and market:
            justtcg = list(market)
            justtcg_fallback = True
            nm_outcome = "fallback"

    if nm_outcome:
        record_justtcg_event(nm_outcome)

    if has_key and not rate_limited:
        try:
            from justtcg_client import psa10_history_for_card

            points, resolved, stats = psa10_history_for_card(
                tcgplayer_id=tcp,
                name=name,
                number=number or None,
                set_name=set_name or None,
            )
            if resolved:
                tcp = str(resolved)
            psa10 = _points_from_rows(points)
            psa10_stats = dict(stats or {})
        except JustTCGRateLimitError:
            rate_limited = True
            psa10_error = "JustTCG rate limited — try again later."
            LOG.warning("psa10_history_for_card rate-limited for %s", card_id)
        except Exception as exc:
            psa10_error = str(exc)[:180]
            LOG.info("psa10_history_for_card failed for %s: %s", card_id, exc)

    if has_key and not rate_limited:
        try:
            from justtcg_client import psa9_history_for_card

            points9, resolved9, stats9 = psa9_history_for_card(
                tcgplayer_id=tcp,
                name=name,
                number=number or None,
                set_name=set_name or None,
            )
            if resolved9:
                tcp = str(resolved9)
            psa9 = _points_from_rows(points9)
            psa9_stats = dict(stats9 or {})
        except JustTCGRateLimitError:
            rate_limited = True
            psa9_error = "JustTCG rate limited — try again later."
            LOG.warning("psa9_history_for_card rate-limited for %s", card_id)
        except Exception as exc:
            psa9_error = str(exc)[:180]
            LOG.info("psa9_history_for_card failed for %s: %s", card_id, exc)

    def _grade_stats(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "has_history_series": bool(raw.get("has_history_series")),
            "period_key": raw.get("period_key"),
            "sales_count": raw.get("sales_count"),
        }

    payload = {
        "card_id": card_id,
        "name": name,
        "set_name": set_name or None,
        "tcgplayer_id": tcp,
        "justtcg_configured": has_key,
        "tcgplayer": market,
        "justtcg": justtcg,
        "justtcg_fallback": justtcg_fallback,
        "justtcg_from_db": justtcg_from_db,
        "justtcg_error": justtcg_error,
        "psa10": psa10,
        "psa10_error": psa10_error,
        "psa10_stats": _grade_stats(psa10_stats),
        "psa9": psa9,
        "psa9_error": psa9_error,
        "psa9_stats": _grade_stats(psa9_stats),
        "cache": "miss",
    }

    # Cache DB-first + successful live payloads. Skip 429 / hard errors.
    if (
        not rate_limited
        and justtcg_error is None
        and psa10_error is None
        and psa9_error is None
    ):
        ttl = (
            _SOURCES_CACHE_TTL_SECONDS
            if (justtcg or psa10 or psa9 or market)
            else _SOURCES_CACHE_EMPTY_TTL_SECONDS
        )
        _cache_put(cache_key, {k: v for k, v in payload.items() if k != "cache"}, ttl=ttl)

    return payload

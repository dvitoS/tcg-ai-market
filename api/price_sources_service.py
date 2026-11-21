"""Multi-source price history for Soft Ink detail (DB + JustTCG NM + PSA 9/10).

PkmnPrices (``PKMN_API_KEY``) fills NM when JustTCG is missing/empty — parallel
cutover path; do not cancel JustTCG until nightly + graded parity is green.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import Future
from datetime import date, timedelta
from typing import Any

from api.catalog_service import load_board, load_card_history
from justtcg_client import JustTCGRateLimitError, justtcg_api_key, normalize_card_number
from services.prices import record_justtcg_event

LOG = logging.getLogger("kestrel.api.price_sources")

# Soft Ink used to live-call JustTCG NM+PSA on every card detail mount.
# Nightly already writes JustTCG NM into price_history — prefer that for NM.
# On 2GB Render we refresh live when DB is modestly stale, capped per day so
# JustTCG 10k/mo and API RSS stay safe (nightly drip still owns bulk fill).
_SOURCES_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_SOURCES_CACHE_LOCK = threading.Lock()
# Long TTL: NM comes from nightly DB; PSA live calls are the Soft Ink quota burn.
_SOURCES_CACHE_TTL_SECONDS = 6 * 60 * 60
_SOURCES_CACHE_EMPTY_TTL_SECONDS = 45 * 60
_SOURCES_CACHE_MAX = 256
_DB_NM_MIN_POINTS = 7
_DB_NM_MAX_AGE_DAYS = 3

# Process-local Soft Ink live NM budget (resets on UTC day / restart).
_LIVE_NM_DAY: str | None = None
_LIVE_NM_USED = 0
_LIVE_NM_LOCK = threading.Lock()

# Single-flight: PriceChart + GradingEv both hit /sources on first paint.
_SOURCES_INFLIGHT: dict[str, Future] = {}
_SOURCES_INFLIGHT_LOCK = threading.Lock()


def clear_price_sources_cache() -> None:
    with _SOURCES_CACHE_LOCK:
        _SOURCES_CACHE.clear()


def reset_live_nm_budget_for_tests() -> None:
    """Test helper — clear the process live-NM counter."""
    global _LIVE_NM_DAY, _LIVE_NM_USED
    with _LIVE_NM_LOCK:
        _LIVE_NM_DAY = None
        _LIVE_NM_USED = 0


def soft_ink_nm_stale_days() -> int:
    """DB NM older than this triggers one live JustTCG NM (default 3)."""
    raw = (os.environ.get("SOFT_INK_NM_STALE_DAYS") or "").strip()
    if raw.isdigit():
        return max(1, min(int(raw), 30))
    return int(_DB_NM_MAX_AGE_DAYS)


def soft_ink_live_nm_daily_budget() -> int | None:
    """Soft Ink live NM calls/day on this process.

    ``None`` = uncapped (still rate-limited by JustTCG). ``0`` = never live
    when DB has enough points. Default ``120`` leaves most of the 10k/mo for
    the nightly drip.
    """
    raw = (os.environ.get("SOFT_INK_LIVE_NM_DAILY_BUDGET") or "120").strip().lower()
    if raw in {"0", "off", "none"}:
        return 0
    if raw in {"unlimited", "inf", "all"}:
        return None
    if raw.isdigit():
        return max(1, min(int(raw), 5000))
    return 120


def soft_ink_pkmn_nm_daily_budget() -> int | None:
    """Soft Ink live PkmnPrices NM calls/day (cutover when JustTCG key absent).

    Default ``200``. ``0`` = never live Pkmn NM (DB-only). ``unlimited`` = no cap.
    """
    raw = (os.environ.get("SOFT_INK_PKMN_NM_DAILY_BUDGET") or "200").strip().lower()
    if raw in {"0", "off", "none"}:
        return 0
    if raw in {"unlimited", "inf", "all"}:
        return None
    if raw.isdigit():
        return max(1, min(int(raw), 5000))
    return 200


_LIVE_PKMN_NM_DAY: str | None = None
_LIVE_PKMN_NM_USED = 0
_LIVE_PKMN_NM_LOCK = threading.Lock()


def reset_live_pkmn_nm_budget_for_tests() -> None:
    global _LIVE_PKMN_NM_DAY, _LIVE_PKMN_NM_USED
    with _LIVE_PKMN_NM_LOCK:
        _LIVE_PKMN_NM_DAY = None
        _LIVE_PKMN_NM_USED = 0


def _try_consume_live_pkmn_nm_budget() -> bool:
    budget = soft_ink_pkmn_nm_daily_budget()
    if budget == 0:
        return False
    if budget is None:
        return True
    global _LIVE_PKMN_NM_DAY, _LIVE_PKMN_NM_USED
    day = date.today().isoformat()
    with _LIVE_PKMN_NM_LOCK:
        if _LIVE_PKMN_NM_DAY != day:
            _LIVE_PKMN_NM_DAY = day
            _LIVE_PKMN_NM_USED = 0
        if _LIVE_PKMN_NM_USED >= budget:
            return False
        _LIVE_PKMN_NM_USED += 1
        return True


def _try_consume_live_nm_budget() -> bool:
    """Return True when a live NM call is allowed and counted."""
    budget = soft_ink_live_nm_daily_budget()
    if budget == 0:
        return False
    today = date.today().isoformat()
    global _LIVE_NM_DAY, _LIVE_NM_USED
    with _LIVE_NM_LOCK:
        if _LIVE_NM_DAY != today:
            _LIVE_NM_DAY = today
            _LIVE_NM_USED = 0
        if budget is not None and _LIVE_NM_USED >= budget:
            return False
        _LIVE_NM_USED += 1
        return True


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
    """True when nightly/DB NM series is fresh enough to skip live JustTCG NM.

    With 2GB Soft Ink we refresh when the last point is older than
    ``SOFT_INK_NM_STALE_DAYS`` (default 3). Sparse series always go live
    (budget permitting). Nightly drip still fills the catalog in bulk.
    """
    if len(market) < _DB_NM_MIN_POINTS:
        return False
    try:
        last = date.fromisoformat(str(market[-1]["date"])[:10])
    except (TypeError, ValueError, KeyError):
        return False
    return last >= date.today() - timedelta(days=soft_ink_nm_stale_days())


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


def normalize_grades_mode(raw: str | None) -> str:
    """none | psa10 | all — default none so Soft Ink detail does not burn graded quota."""
    value = str(raw or "none").strip().lower()
    if value in {"1", "true", "yes", "on", "psa10", "10"}:
        return "psa10"
    if value in {"all", "both", "psa9", "full"}:
        return "all"
    return "none"


def _fetch_psa_pair(
    *,
    tcp: str | None,
    name: str,
    number: str,
    set_name: str,
    grades: str = "psa10",
) -> tuple[
    list[dict[str, Any]],
    str | None,
    dict[str, Any],
    list[dict[str, Any]],
    str | None,
    dict[str, Any],
    str | None,
    bool,
]:
    """Fetch PSA grades in one JustTCG call (grade=10 or grade=9,10)."""
    from justtcg_client import psa_histories_for_card

    mode = normalize_grades_mode(grades)
    psa10: list[dict[str, Any]] = []
    psa10_error: str | None = None
    psa10_stats: dict[str, Any] = {}
    psa9: list[dict[str, Any]] = []
    psa9_error: str | None = None
    psa9_stats: dict[str, Any] = {}
    rate_limited = False
    resolved_tcp = tcp

    if mode == "none":
        return (
            psa10,
            psa10_error,
            psa10_stats,
            psa9,
            psa9_error,
            psa9_stats,
            resolved_tcp,
            False,
        )

    wanted = [10.0, 9.0] if mode == "all" else [10.0]
    try:
        bundle, resolved = psa_histories_for_card(
            grades=wanted,
            tcgplayer_id=tcp,
            name=name,
            number=number or None,
            set_name=set_name or None,
        )
        if resolved:
            resolved_tcp = str(resolved)
        points10, stats10 = bundle.get(10.0, ([], {}))
        psa10 = _points_from_rows(points10)
        psa10_stats = dict(stats10 or {})
        if mode == "all":
            points9, stats9 = bundle.get(9.0, ([], {}))
            psa9 = _points_from_rows(points9)
            psa9_stats = dict(stats9 or {})
    except JustTCGRateLimitError:
        rate_limited = True
        psa10_error = "JustTCG rate limited — try again later."
        if mode == "all":
            psa9_error = psa10_error
        LOG.warning("psa_histories_for_card rate-limited for %s", name)
    except Exception as exc:
        psa10_error = str(exc)[:180]
        if mode == "all":
            psa9_error = psa10_error
        LOG.info("psa_histories_for_card failed for %s: %s", name, exc)

    return (
        psa10,
        psa10_error,
        psa10_stats,
        psa9,
        psa9_error,
        psa9_stats,
        resolved_tcp,
        rate_limited,
    )


def _printing_cache_slug(printing: str | None) -> str:
    text = str(printing or "").strip().lower()
    if not text:
        return "-"
    slug = "".join(ch if ch.isalnum() else "" for ch in text)
    return (slug[:40] or "-")


def _condition_cache_slug(condition: str | None) -> str:
    try:
        from services.lot_price_adjust import normalize_condition

        code = normalize_condition(condition or "NM")
    except Exception:
        code = str(condition or "NM").strip().upper() or "NM"
    return code if code != "NM" else "-"


def _build_card_price_sources_uncached(
    card_id: str,
    *,
    limit: int,
    grades: str = "none",
    cardmarket: bool = False,
    printing: str | None = None,
    condition: str | None = None,
) -> dict[str, Any]:
    grades_mode = normalize_grades_mode(grades)
    want_cardmarket = bool(cardmarket)
    finish_label = str(printing or "").strip() or None
    try:
        from services.lot_price_adjust import normalize_condition

        condition_code = normalize_condition(condition or "NM")
    except Exception:
        condition_code = str(condition or "NM").strip().upper() or "NM"
    want_non_nm = condition_code != "NM"
    try:
        from pkmnprices_client import soft_ink_finish_to_pkmn_variant

        want_variant = soft_ink_finish_to_pkmn_variant(finish_label)
    except Exception:
        want_variant = finish_label
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

    # Fresh DB / live JustTCG history is NM-only. LP/MP must not inherit that series —
    # otherwise the chart looks like the selected condition while plotting NM.
    if not want_non_nm:
        # Fresh DB history is primary whether or not JustTCG is configured
        # (cutover: Soft Ink must keep working with PKMN_API_KEY alone).
        if use_db_nm:
            justtcg = list(market)
            justtcg_from_db = True
            nm_outcome = "db"
            LOG.info(
                "using DB NM history for %s (%s pts) — skip live NM",
                card_id,
                len(market),
            )
        elif grades_mode != "none":
            # Graded follow-up: reuse DB market for NM — never spend a second live NM call.
            if market:
                justtcg = list(market)
                justtcg_from_db = True
                nm_outcome = "db"
            else:
                nm_outcome = None
        elif has_key:
            if not _try_consume_live_nm_budget():
                # Daily Soft Ink live budget exhausted — serve stale DB, don't crash quota.
                if market:
                    justtcg = list(market)
                    justtcg_from_db = True
                    nm_outcome = "db"
                    LOG.info(
                        "live NM budget exhausted — using DB for %s (%s pts)",
                        card_id,
                        len(market),
                    )
                else:
                    nm_outcome = None
                    justtcg_error = "JustTCG live NM daily budget exhausted."
            else:
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
        elif market:
            # No JustTCG key — still paint the chart series from DB; live Pkmn may refresh below.
            justtcg = list(market)
            justtcg_from_db = True
            nm_outcome = "db"

        if nm_outcome and has_key:
            record_justtcg_event(nm_outcome)

    # PkmnPrices: fill empty NM, or refresh when JustTCG key is gone and DB was stale.
    pkmn_configured = False
    pkmn_used = False
    pkmn_error: str | None = None
    try:
        from pkmnprices_client import (
            PkmnPricesRateLimitError,
            nm_history_for_tcgplayer_id,
            pkmnprices_configured,
        )

        pkmn_configured = bool(pkmnprices_configured())
    except Exception:
        pkmn_configured = False

    # Finish / non-NM condition must come from PkmnPrices — DB Soft Ink history is NM-only + finish-blind.
    want_pkmn_nm = bool(
        pkmn_configured
        and tcp
        and (
            bool(want_variant)
            or want_non_nm
            or not justtcg
            or (not has_key and not use_db_nm and grades_mode == "none")
        )
    )
    if want_pkmn_nm:
        if not _try_consume_live_pkmn_nm_budget():
            if want_non_nm:
                justtcg = []
                justtcg_from_db = False
                justtcg_fallback = False
                pkmn_error = "PkmnPrices Soft Ink live NM daily budget exhausted."
            elif not justtcg and market:
                justtcg = list(market)
                justtcg_from_db = True
                justtcg_fallback = True
            elif not justtcg:
                pkmn_error = "PkmnPrices Soft Ink live NM daily budget exhausted."
            elif want_variant:
                pkmn_error = "PkmnPrices Soft Ink live NM daily budget exhausted."
        else:
            try:
                # Soft Ink charts (NM/LP/MP + 1Y): always ask for a year window.
                # JustTCG is 1 req either way; PkmnPrices bills per row returned —
                # DB-first + daily budget + 6h cache keep credit burn bounded.
                hist_limit = max(1, min(365, int(limit)))
                hist_period = "365d"
                points = nm_history_for_tcgplayer_id(
                    tcp,
                    period=hist_period,
                    limit=hist_limit,
                    variant=want_variant,
                    condition=condition_code,
                )
                filled = _points_from_rows(points)
                if filled:
                    justtcg = filled
                    pkmn_used = True
                    justtcg_from_db = False
                    justtcg_fallback = True
                    LOG.info(
                        "PkmnPrices %s for %s (%s pts, tcp=%s, variant=%s)",
                        condition_code,
                        card_id,
                        len(justtcg),
                        tcp,
                        want_variant or "auto",
                    )
                else:
                    pkmn_error = (
                        f"PkmnPrices returned no {condition_code} history"
                        + (f" for {want_variant}." if want_variant else ".")
                    )
                    if want_non_nm:
                        justtcg = []
                        justtcg_from_db = False
                        justtcg_fallback = False
                    elif not justtcg and market:
                        justtcg = list(market)
                        justtcg_from_db = True
                        justtcg_fallback = True
            except PkmnPricesRateLimitError:
                pkmn_error = "PkmnPrices rate/credit limited — try again later."
                LOG.warning("PkmnPrices rate-limited for %s", card_id)
                if want_non_nm:
                    justtcg = []
                    justtcg_from_db = False
                    justtcg_fallback = False
                elif not justtcg and market:
                    justtcg = list(market)
                    justtcg_from_db = True
                    justtcg_fallback = True
            except Exception as exc:
                pkmn_error = str(exc)[:180]
                LOG.info("PkmnPrices NM fill failed for %s: %s", card_id, exc)
                if want_non_nm:
                    justtcg = []
                    justtcg_from_db = False
                    justtcg_fallback = False
                elif not justtcg and market:
                    justtcg = list(market)
                    justtcg_from_db = True
                    justtcg_fallback = True
    elif want_non_nm and not justtcg:
        if not pkmn_configured:
            pkmn_error = f"PkmnPrices required for {condition_code} history."
        elif not tcp:
            pkmn_error = (
                f"No TCGplayer id — cannot load {condition_code} history."
            )

    # Cardmarket history (EUR) — opt-in so Soft Ink detail does not burn credits until the CM tab opens.
    cardmarket_series: list[dict[str, Any]] = []
    cardmarket_error: str | None = None
    if want_cardmarket:
        cardmarket_series, cardmarket_error, cm_used = _fetch_cardmarket_series_only(
            tcp=tcp,
            limit=limit,
            pkmn_configured=pkmn_configured,
            variant=want_variant,
            condition=condition_code,
        )
        if cm_used:
            pkmn_used = True
            LOG.info(
                "PkmnPrices Cardmarket NM for %s (%s pts, tcp=%s)",
                card_id,
                len(cardmarket_series),
                tcp,
            )

    # Graded prints are optional — default Soft Ink detail skips them (quota).
    pkmn_grades_used = False
    if has_key and not rate_limited and grades_mode != "none":
        (
            psa10,
            psa10_error,
            psa10_stats,
            psa9,
            psa9_error,
            psa9_stats,
            tcp,
            psa_rate_limited,
        ) = _fetch_psa_pair(
            tcp=tcp,
            name=name,
            number=number,
            set_name=set_name,
            grades=grades_mode,
        )
        if psa_rate_limited:
            rate_limited = True

    # PkmnPrices PSA fallback — eBay comps → daily median series (JustTCG primary).
    if pkmn_configured and tcp and grades_mode != "none":
        try:
            from pkmnprices_client import (
                PkmnPricesRateLimitError,
                psa_history_for_tcgplayer_id,
            )

            want_psa9 = grades_mode == "all"
            # Match Soft Ink 1Y graded toggle — eBay comps window was stuck at 90d.
            psa_hist_period = "365d"
            psa_hist_limit = 20  # PkmnPrices eBay page max
            if not psa10:
                try:
                    pts, stats = psa_history_for_tcgplayer_id(
                        tcp,
                        grade=10,
                        period=psa_hist_period,
                        limit=psa_hist_limit,
                    )
                    psa10 = _points_from_rows(pts)
                    if psa10:
                        psa10_stats = dict(stats or {})
                        psa10_error = None
                        pkmn_grades_used = True
                        pkmn_used = True
                        LOG.info(
                            "PkmnPrices PSA10 fallback for %s (%s pts, tcp=%s, %s)",
                            card_id,
                            len(psa10),
                            tcp,
                            psa_hist_period,
                        )
                    elif not psa10_error:
                        psa10_error = "PkmnPrices returned no PSA 10 eBay comps."
                except PkmnPricesRateLimitError:
                    if not psa10_error:
                        psa10_error = "PkmnPrices rate/credit limited — try again later."
                except Exception as exc:
                    if not psa10_error:
                        psa10_error = str(exc)[:180]
                    LOG.info("PkmnPrices PSA10 fallback failed for %s: %s", card_id, exc)

            if want_psa9 and not psa9:
                try:
                    pts, stats = psa_history_for_tcgplayer_id(
                        tcp,
                        grade=9,
                        period=psa_hist_period,
                        limit=psa_hist_limit,
                    )
                    psa9 = _points_from_rows(pts)
                    if psa9:
                        psa9_stats = dict(stats or {})
                        psa9_error = None
                        pkmn_grades_used = True
                        pkmn_used = True
                        LOG.info(
                            "PkmnPrices PSA9 fallback for %s (%s pts, tcp=%s, %s)",
                            card_id,
                            len(psa9),
                            tcp,
                            psa_hist_period,
                        )
                    elif not psa9_error:
                        psa9_error = "PkmnPrices returned no PSA 9 eBay comps."
                except PkmnPricesRateLimitError:
                    if not psa9_error:
                        psa9_error = "PkmnPrices rate/credit limited — try again later."
                except Exception as exc:
                    if not psa9_error:
                        psa9_error = str(exc)[:180]
                    LOG.info("PkmnPrices PSA9 fallback failed for %s: %s", card_id, exc)
        except Exception as exc:
            LOG.info("PkmnPrices graded import failed: %s", exc)

    # Graded population (Pro+) — seeds Grading EV gem-rate; 1 credit when grades armed.
    population: dict[str, Any] | None = None
    population_error: str | None = None
    if pkmn_configured and tcp and grades_mode != "none":
        try:
            from pkmnprices_client import (
                PkmnPricesRateLimitError,
                population_for_tcgplayer_id,
            )

            population = population_for_tcgplayer_id(tcp)
            if population:
                pkmn_used = True
                LOG.info(
                    "PkmnPrices population for %s (variant=%s psa10=%s gem=%.2f)",
                    card_id,
                    population.get("variant"),
                    population.get("psa_10"),
                    float(population.get("gem_rate_for_ev") or 0),
                )
        except PkmnPricesRateLimitError:
            population_error = "PkmnPrices rate/credit limited — try again later."
        except Exception as exc:
            population_error = str(exc)[:180]
            LOG.info("PkmnPrices population failed for %s: %s", card_id, exc)

    def _grade_stats(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "has_history_series": bool(raw.get("has_history_series")),
            "period_key": raw.get("period_key"),
            "sales_count": raw.get("sales_count"),
            "price_status": raw.get("price_status"),
            "last_sale_at": raw.get("last_sale_at"),
            "price_expires_at": raw.get("price_expires_at"),
            "price": raw.get("price"),
            "canonical": raw.get("canonical"),
        }

    payload = {
        "card_id": card_id,
        "name": name,
        "set_name": set_name or None,
        "tcgplayer_id": tcp,
        "justtcg_configured": has_key,
        "pkmnprices_configured": pkmn_configured,
        "pkmnprices_used": pkmn_used,
        "pkmnprices_grades_used": pkmn_grades_used,
        "pkmnprices_error": pkmn_error,
        "tcgplayer": market,
        "justtcg": justtcg,
        "justtcg_fallback": justtcg_fallback,
        "justtcg_from_db": justtcg_from_db,
        "justtcg_error": justtcg_error,
        "cardmarket": cardmarket_series,
        "cardmarket_error": cardmarket_error,
        "psa10": psa10,
        "psa10_error": psa10_error,
        "psa10_stats": _grade_stats(psa10_stats),
        "psa9": psa9,
        "psa9_error": psa9_error,
        "psa9_stats": _grade_stats(psa9_stats),
        "population": population,
        "population_error": population_error,
        "grades": grades_mode,
        "printing": finish_label,
        "condition": condition_code if want_non_nm else None,
        "cache": "miss",
    }

    # Cache DB-first + successful live payloads. Skip 429 / hard NM+PSA10 errors.
    # PSA 9 is additive — a soft PSA 9 miss must not poison the cache entry.
    # Soft Cardmarket miss is additive too (EUR series is opt-in).
    if not rate_limited and justtcg_error is None and psa10_error is None:
        ttl = (
            _SOURCES_CACHE_TTL_SECONDS
            if (justtcg or psa10 or psa9 or market or cardmarket_series)
            else _SOURCES_CACHE_EMPTY_TTL_SECONDS
        )
        _cache_put(
            cache_key=(
                f"v6|{card_id}|{limit}|{grades_mode}|cm={int(want_cardmarket)}"
                f"|p={_printing_cache_slug(finish_label)}"
                f"|c={_condition_cache_slug(condition_code)}"
            ),
            payload={k: v for k, v in payload.items() if k != "cache"},
            ttl=ttl,
        )

    return payload


def _fetch_cardmarket_series_only(
    *,
    tcp: str | None,
    limit: int,
    pkmn_configured: bool,
    variant: str | None = None,
    condition: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, bool]:
    """EUR history only — used when Soft Ink already has a cm=0 sources cache hit."""
    if not pkmn_configured:
        return [], "PkmnPrices not configured for Cardmarket history.", False
    if not tcp:
        return [], "No TCGplayer id to resolve Cardmarket history.", False
    if not _try_consume_live_pkmn_nm_budget():
        return [], "PkmnPrices Soft Ink live NM daily budget exhausted.", False
    try:
        from pkmnprices_client import (
            PkmnPricesRateLimitError,
            nm_history_for_tcgplayer_id,
        )

        hist_limit = max(1, min(365, int(limit)))
        hist_period = "365d"
        cond = condition or "NM"
        cm_points = nm_history_for_tcgplayer_id(
            tcp,
            period=hist_period,
            limit=hist_limit,
            currency="eur",
            variant=variant,
            condition=cond,
        )
        series = _points_from_rows(cm_points)
        if series:
            return series, None, True
        label = cond if cond != "NM" else "Near Mint"
        if variant:
            return (
                [],
                f"PkmnPrices returned no Cardmarket {label} history for {variant}.",
                False,
            )
        return [], f"PkmnPrices returned no Cardmarket {label} history.", False
    except PkmnPricesRateLimitError:
        return [], "PkmnPrices rate/credit limited — try again later.", False
    except Exception as exc:
        return [], str(exc)[:180], False


def build_card_price_sources(
    card_id: str,
    *,
    limit: int = 180,
    grades: str | None = "none",
    cardmarket: bool = False,
    printing: str | None = None,
    condition: str | None = None,
) -> dict[str, Any]:
    card_id = str(card_id).strip()
    limit = max(1, min(int(limit or 180), 365))
    grades_mode = normalize_grades_mode(grades)
    want_cardmarket = bool(cardmarket)
    finish_label = str(printing or "").strip() or None
    try:
        from services.lot_price_adjust import normalize_condition

        condition_code = normalize_condition(condition or "NM")
    except Exception:
        condition_code = str(condition or "NM").strip().upper() or "NM"
    print_slug = _printing_cache_slug(finish_label)
    cond_slug = _condition_cache_slug(condition_code)
    cache_key = (
        f"v6|{card_id}|{limit}|{grades_mode}|cm={int(want_cardmarket)}"
        f"|p={print_slug}|c={cond_slug}"
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        cached["cache"] = "hit"
        record_justtcg_event("cache_hit")
        return cached

    # Soft Ink CM tab: reuse USD sources cache so we do not re-burn Pkmn USD credits.
    if want_cardmarket:
        base_key = (
            f"v6|{card_id}|{limit}|{grades_mode}|cm=0|p={print_slug}|c={cond_slug}"
        )
        base = _cache_get(base_key)
        if base is not None:
            try:
                from pkmnprices_client import soft_ink_finish_to_pkmn_variant

                cm_variant = soft_ink_finish_to_pkmn_variant(finish_label)
            except Exception:
                cm_variant = finish_label
            series, cm_err, used = _fetch_cardmarket_series_only(
                tcp=base.get("tcgplayer_id"),
                limit=limit,
                pkmn_configured=bool(base.get("pkmnprices_configured")),
                variant=cm_variant,
                condition=condition_code,
            )
            payload = dict(base)
            payload["cardmarket"] = series
            payload["cardmarket_error"] = cm_err
            payload["printing"] = finish_label
            payload["condition"] = (
                condition_code if condition_code != "NM" else None
            )
            if used:
                payload["pkmnprices_used"] = True
            payload["cache"] = "miss"
            ttl = (
                _SOURCES_CACHE_TTL_SECONDS
                if series
                else _SOURCES_CACHE_EMPTY_TTL_SECONDS
            )
            _cache_put(
                cache_key=cache_key,
                payload={k: v for k, v in payload.items() if k != "cache"},
                ttl=ttl,
            )
            return payload

    owner = False
    with _SOURCES_INFLIGHT_LOCK:
        inflight = _SOURCES_INFLIGHT.get(cache_key)
        if inflight is None:
            inflight = Future()
            _SOURCES_INFLIGHT[cache_key] = inflight
            owner = True

    if not owner:
        result = inflight.result()
        payload = dict(result)
        payload["cache"] = "hit"
        record_justtcg_event("cache_hit")
        return payload

    try:
        payload = _build_card_price_sources_uncached(
            card_id,
            limit=limit,
            grades=grades_mode,
            cardmarket=want_cardmarket,
            printing=finish_label,
            condition=condition_code,
        )
        inflight.set_result({k: v for k, v in payload.items() if k != "cache"})
        return payload
    except Exception as exc:
        inflight.set_exception(exc)
        raise
    finally:
        with _SOURCES_INFLIGHT_LOCK:
            current = _SOURCES_INFLIGHT.get(cache_key)
            if current is inflight:
                _SOURCES_INFLIGHT.pop(cache_key, None)

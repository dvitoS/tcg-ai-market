"""Live price load helpers + JustTCG fetch observability.

Counters work in both Streamlit (per session when a script context exists)
and Soft Ink / FastAPI (process-wide in-memory totals).
"""

from __future__ import annotations

import threading
from typing import Any

_OBS_KEYS = ("live", "db", "empty", "fallback", "error", "cache_hit")
_PROCESS_OBS: dict[str, int] = {k: 0 for k in _OBS_KEYS}
_PROCESS_LOCK = threading.Lock()


def _blank_stats() -> dict[str, int]:
    return {k: 0 for k in _OBS_KEYS}


def _streamlit_stats() -> dict[str, int] | None:
    """Return Streamlit session bucket when running inside a script context.

    Soft Ink / FastAPI never imports Streamlit here — process counters only.
    """
    import sys

    if "streamlit" not in sys.modules:
        return None
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        if get_script_run_ctx() is None:
            return None
        bucket = st.session_state.setdefault("_justtcg_obs", _blank_stats())
        for key in _OBS_KEYS:
            bucket.setdefault(key, 0)
        return bucket
    except Exception:
        return None


def record_justtcg_event(kind: str) -> None:
    if kind not in _OBS_KEYS:
        return
    session = _streamlit_stats()
    if session is not None:
        session[kind] = int(session.get(kind) or 0) + 1
        return
    with _PROCESS_LOCK:
        _PROCESS_OBS[kind] = int(_PROCESS_OBS.get(kind) or 0) + 1


def reset_justtcg_observability() -> None:
    """Zero process counters (Soft Ink / API). Streamlit session is left alone."""
    with _PROCESS_LOCK:
        for key in _OBS_KEYS:
            _PROCESS_OBS[key] = 0


def justtcg_observability_summary() -> dict[str, Any]:
    session = _streamlit_stats()
    if session is not None:
        stats = {k: int(session.get(k) or 0) for k in _OBS_KEYS}
    else:
        with _PROCESS_LOCK:
            stats = {k: int(_PROCESS_OBS.get(k) or 0) for k in _OBS_KEYS}

    # Successful / attempted NM resolutions (exclude pure cache hits from miss %).
    total = (
        int(stats.get("live", 0))
        + int(stats.get("db", 0))
        + int(stats.get("empty", 0))
        + int(stats.get("fallback", 0))
    )
    miss = int(stats.get("empty", 0)) + int(stats.get("fallback", 0))
    rate = (miss / total * 100.0) if total else 0.0
    return {
        **stats,
        "attempts": total,
        "miss_or_fallback_pct": rate,
    }


def clear_live_price_caches(*, card_id: str | None = None) -> int:
    """Drop session caches for JustTCG / PSA10 / eBay (optionally one card)."""
    import sys

    removed = 0
    needle = str(card_id) if card_id else None
    if "streamlit" in sys.modules:
        try:
            import streamlit as st
            from streamlit.runtime.scriptrunner import get_script_run_ctx

            if get_script_run_ctx() is not None:
                for key in list(st.session_state.keys()):
                    text = str(key)
                    if not text.startswith(
                        ("justtcg_series::", "psa10_series::", "ebay_listings::")
                    ):
                        continue
                    if needle and needle not in text:
                        continue
                    del st.session_state[key]
                    removed += 1
        except Exception:
            pass
    try:
        from justtcg_client import clear_justtcg_cache

        clear_justtcg_cache()
    except Exception:
        pass
    try:
        from api.price_sources_service import clear_price_sources_cache

        clear_price_sources_cache()
    except Exception:
        pass
    return removed

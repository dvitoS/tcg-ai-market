"""Live price load helpers + JustTCG fetch observability."""

from __future__ import annotations

from typing import Any

import streamlit as st


def _stats() -> dict[str, int]:
    bucket = st.session_state.setdefault(
        "_justtcg_obs",
        {"live": 0, "empty": 0, "fallback": 0, "error": 0, "cache_hit": 0},
    )
    return bucket


def record_justtcg_event(kind: str) -> None:
    stats = _stats()
    if kind in stats:
        stats[kind] = int(stats[kind]) + 1


def justtcg_observability_summary() -> dict[str, Any]:
    stats = dict(_stats())
    total = int(stats.get("live", 0)) + int(stats.get("empty", 0)) + int(stats.get("fallback", 0))
    miss = int(stats.get("empty", 0)) + int(stats.get("fallback", 0))
    rate = (miss / total * 100.0) if total else 0.0
    return {
        **stats,
        "attempts": total,
        "miss_or_fallback_pct": rate,
    }


def clear_live_price_caches(*, card_id: str | None = None) -> int:
    """Drop session caches for JustTCG / PSA10 / eBay (optionally one card)."""
    removed = 0
    needle = str(card_id) if card_id else None
    for key in list(st.session_state.keys()):
        text = str(key)
        if not text.startswith(("justtcg_series::", "psa10_series::", "ebay_listings::")):
            continue
        if needle and needle not in text:
            continue
        del st.session_state[key]
        removed += 1
    try:
        from justtcg_client import clear_justtcg_cache

        clear_justtcg_cache()
    except Exception:
        pass
    return removed

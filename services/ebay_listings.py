"""Session-cached eBay Browse + sold comps helpers."""

from __future__ import annotations

from typing import Any

import streamlit as st


def _ebay_module():
    import ebay_client as ebay

    return ebay


def load_ebay_listings(
    *,
    card_id: str,
    name: str,
    set_name: str,
) -> tuple[list[dict], str | None]:
    ebay = _ebay_module()
    if not ebay.ebay_configured():
        return [], None

    number = ""
    if "-" in str(card_id):
        number = str(card_id).rsplit("-", 1)[-1].lstrip("0") or str(card_id).rsplit("-", 1)[-1]

    cache_key = f"ebay_listings::{card_id}"
    cached = st.session_state.get(cache_key)
    if isinstance(cached, list) and cached:
        return cached, None

    try:
        rows = ebay.listings_for_card(
            name=name,
            set_name=set_name or None,
            number=number or None,
            limit=8,
        )
    except Exception as exc:
        return [], str(exc)

    if rows:
        st.session_state[cache_key] = rows
    return rows, None


def load_ebay_sold_comps(
    *,
    card_id: str,
    name: str,
    set_name: str,
) -> tuple[list[dict[str, Any]], str | None, dict[str, float | None]]:
    """Returns (rows, hint, stats). stats has min/median/max when priced rows exist."""
    ebay = _ebay_module()
    empty_stats: dict[str, float | None] = {"min": None, "median": None, "max": None, "n": 0}
    if not ebay.ebay_configured() or not hasattr(ebay, "sold_comps_for_card"):
        return [], "eBay credentials missing.", empty_stats

    cache_key = f"ebay_sold::{card_id}"
    cached = st.session_state.get(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("rows"), list):
        return list(cached["rows"]), cached.get("hint"), dict(cached.get("stats") or empty_stats)

    number = ""
    if "-" in str(card_id):
        number = str(card_id).rsplit("-", 1)[-1]

    try:
        rows, hint = ebay.sold_comps_for_card(
            name=name,
            set_name=set_name or None,
            number=number or None,
            limit=8,
        )
    except Exception as exc:
        return [], str(exc)[:180], empty_stats

    prices = sorted(
        float(r["price"]) for r in rows if isinstance(r, dict) and r.get("price") is not None
    )
    stats: dict[str, float | None] = {
        "min": prices[0] if prices else None,
        "max": prices[-1] if prices else None,
        "median": prices[len(prices) // 2] if prices else None,
        "n": float(len(prices)),
    }
    st.session_state[cache_key] = {"rows": rows, "hint": hint, "stats": stats}
    return rows, hint, stats

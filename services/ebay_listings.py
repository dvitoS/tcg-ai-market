"""Session-cached eBay Browse + sold comps helpers."""

from __future__ import annotations

from typing import Any

import streamlit as st


def _ebay_module():
    import ebay_client as ebay

    return ebay


def _card_number(card_id: str) -> str:
    text = str(card_id or "")
    if "-" not in text:
        return ""
    return text.rsplit("-", 1)[-1]


def _price_stats(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    prices = sorted(
        float(r["price"]) for r in rows if isinstance(r, dict) and r.get("price") is not None
    )
    return {
        "min": prices[0] if prices else None,
        "max": prices[-1] if prices else None,
        "median": prices[len(prices) // 2] if prices else None,
        "n": float(len(prices)),
    }


def _as_active_comps(listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tag Browse rows so the UI can label them as active (not sold)."""
    out: list[dict[str, Any]] = []
    for row in listings:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["comp_source"] = "active"
        item["sold_date"] = ""
        item["is_sold"] = False
        out.append(item)
    return out


def load_ebay_listings(
    *,
    card_id: str,
    name: str,
    set_name: str,
) -> tuple[list[dict], str | None]:
    ebay = _ebay_module()
    if not ebay.ebay_configured():
        return [], None

    number = _card_number(card_id)
    number = number.lstrip("0") or number

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
    """Returns (rows, hint, stats).

    Prefer Marketplace Insights sold sales. When gated/empty, fall back to
    active Browse listings tagged ``comp_source="active"`` (not sold history).
    """
    ebay = _ebay_module()
    empty_stats: dict[str, float | None] = {"min": None, "median": None, "max": None, "n": 0}
    if not ebay.ebay_configured() or not hasattr(ebay, "sold_comps_for_card"):
        return [], "eBay credentials missing.", empty_stats

    cache_key = f"ebay_sold::{card_id}"
    cached = st.session_state.get(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("rows"), list):
        return list(cached["rows"]), cached.get("hint"), dict(cached.get("stats") or empty_stats)

    number = _card_number(card_id)
    hint: str | None = None
    rows: list[dict[str, Any]] = []

    try:
        rows, hint = ebay.sold_comps_for_card(
            name=name,
            set_name=set_name or None,
            number=number or None,
            limit=8,
        )
    except Exception as exc:
        rows, hint = [], str(exc)[:180]

    # Mark true sold rows.
    for row in rows:
        if isinstance(row, dict):
            row.setdefault("comp_source", "sold")
            row.setdefault("is_sold", True)

    # Insights gated / empty → reuse Browse listings as valuation proxy.
    if not rows:
        active, active_err = load_ebay_listings(
            card_id=card_id,
            name=name,
            set_name=set_name,
        )
        if active:
            rows = _as_active_comps(active)
            hint = hint or (
                "eBay Marketplace Insights unavailable — showing active listings "
                "(asking prices, not completed sales)."
            )
        elif active_err and not hint:
            hint = active_err[:180]

    stats = _price_stats(rows)
    # Flag for UI: sold vs active fallback.
    stats["is_sold"] = 1.0 if rows and all(r.get("is_sold", True) for r in rows) else 0.0
    st.session_state[cache_key] = {"rows": rows, "hint": hint, "stats": stats}
    return rows, hint, stats

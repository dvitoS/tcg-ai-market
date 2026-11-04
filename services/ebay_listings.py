"""eBay Browse + sold comps helpers (API + Streamlit)."""

from __future__ import annotations

from typing import Any

import ebay_client as ebay
from services.epn import epn_configured, tag_listing_urls


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


def _affiliate_rows(rows: list[dict[str, Any]], *, customid: str) -> list[dict[str, Any]]:
    if not rows:
        return []
    copied = [dict(r) for r in rows if isinstance(r, dict)]
    return tag_listing_urls(copied, customid=customid)


def fetch_ebay_listings(
    *,
    card_id: str,
    name: str,
    set_name: str,
    limit: int = 8,
) -> tuple[list[dict[str, Any]], str | None]:
    """Active Browse listings without Streamlit session cache."""
    if not ebay.ebay_configured():
        return [], "eBay credentials missing."

    number = _card_number(card_id)
    number = number.lstrip("0") or number
    try:
        rows = ebay.listings_for_card(
            name=name,
            set_name=set_name or None,
            number=number or None,
            limit=limit,
        )
    except Exception as exc:
        return [], str(exc)[:220]

    return _affiliate_rows(rows, customid=f"detail-active-{card_id}"), None


def fetch_ebay_sold_comps(
    *,
    card_id: str,
    name: str,
    set_name: str,
    limit: int = 8,
) -> tuple[list[dict[str, Any]], str | None, dict[str, float | None]]:
    """Sold comps (or active fallback). No Streamlit session cache."""
    empty_stats: dict[str, float | None] = {"min": None, "median": None, "max": None, "n": 0.0}
    if not ebay.ebay_configured() or not hasattr(ebay, "sold_comps_for_card"):
        return [], "eBay credentials missing.", empty_stats

    number = _card_number(card_id)
    hint: str | None = None
    rows: list[dict[str, Any]] = []

    try:
        rows, hint = ebay.sold_comps_for_card(
            name=name,
            set_name=set_name or None,
            number=number or None,
            limit=limit,
        )
    except Exception as exc:
        rows, hint = [], str(exc)[:180]

    for row in rows:
        if isinstance(row, dict):
            row.setdefault("comp_source", "sold")
            row.setdefault("is_sold", True)

    if not rows:
        active, active_err = fetch_ebay_listings(
            card_id=card_id,
            name=name,
            set_name=set_name,
            limit=limit,
        )
        # fetch_ebay_listings already affiliate-tagged; re-tag source only.
        if active:
            # Strip prior affiliate customid path by rebuilding from raw fields —
            # active rows are already tagged; just mark as active comps.
            rows = _as_active_comps(active)
            hint = None
        elif active_err and not hint:
            hint = active_err[:180]
    else:
        rows = _affiliate_rows(rows, customid=f"detail-sold-{card_id}")

    stats = _price_stats(rows)
    stats["is_sold"] = 1.0 if rows and all(r.get("is_sold", True) for r in rows) else 0.0
    return rows, hint, stats


def build_ebay_detail_payload(
    *,
    card_id: str,
    name: str,
    set_name: str = "",
    limit: int = 8,
) -> dict[str, Any]:
    """JSON-ready payload for Soft Ink / FastAPI."""
    configured = bool(ebay.ebay_configured())
    listings, listings_error = (
        fetch_ebay_listings(card_id=card_id, name=name, set_name=set_name, limit=limit)
        if configured
        else ([], "eBay credentials missing.")
    )
    sold_rows, sold_hint, sold_stats = (
        fetch_ebay_sold_comps(card_id=card_id, name=name, set_name=set_name, limit=limit)
        if configured
        else ([], "eBay credentials missing.", {"min": None, "median": None, "max": None, "n": 0.0})
    )
    is_sold = bool(sold_stats.get("is_sold", 0.0))
    return {
        "configured": configured,
        "epn": bool(epn_configured()),
        "listings": listings,
        "listings_error": listings_error,
        "sold": sold_rows if is_sold else [],
        "sold_hint": sold_hint,
        "sold_stats": {
            "min": sold_stats.get("min"),
            "median": sold_stats.get("median"),
            "max": sold_stats.get("max"),
            "n": int(sold_stats.get("n") or 0),
            "is_sold": is_sold,
        },
        "sold_fallback_active": bool(sold_rows) and not is_sold,
        "active_fallback": [] if is_sold else sold_rows,
    }


# --- Streamlit session-cached wrappers (keep Explore UX snappy) -----------------


def load_ebay_listings(
    *,
    card_id: str,
    name: str,
    set_name: str,
) -> tuple[list[dict], str | None]:
    import streamlit as st

    if not ebay.ebay_configured():
        return [], None

    cache_key = f"ebay_listings::{card_id}"
    cached = st.session_state.get(cache_key)
    if isinstance(cached, list) and cached:
        return cached, None

    rows, err = fetch_ebay_listings(card_id=card_id, name=name, set_name=set_name)
    # Streamlit UI applies EPN itself; return untagged-ish by re-fetching raw if needed.
    # Prefer raw client rows for Streamlit (it tags in the template).
    if err:
        return [], err
    number = _card_number(card_id)
    number = number.lstrip("0") or number
    try:
        raw = ebay.listings_for_card(
            name=name,
            set_name=set_name or None,
            number=number or None,
            limit=8,
        )
    except Exception as exc:
        return [], str(exc)
    if raw:
        st.session_state[cache_key] = raw
    return raw, None


def load_ebay_sold_comps(
    *,
    card_id: str,
    name: str,
    set_name: str,
) -> tuple[list[dict[str, Any]], str | None, dict[str, float | None]]:
    import streamlit as st

    empty_stats: dict[str, float | None] = {"min": None, "median": None, "max": None, "n": 0}
    if not ebay.ebay_configured() or not hasattr(ebay, "sold_comps_for_card"):
        return [], "eBay credentials missing.", empty_stats

    cache_key = f"ebay_sold_v2::{card_id}"
    cached = st.session_state.get(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("rows"), list):
        return list(cached["rows"]), cached.get("hint"), dict(cached.get("stats") or empty_stats)

    # Build without affiliate tags for Streamlit (UI tags links).
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

    for row in rows:
        if isinstance(row, dict):
            row.setdefault("comp_source", "sold")
            row.setdefault("is_sold", True)

    if not rows:
        active, active_err = load_ebay_listings(
            card_id=card_id,
            name=name,
            set_name=set_name,
        )
        if active:
            rows = _as_active_comps(active)
            hint = None
        elif active_err and not hint:
            hint = active_err[:180]

    stats = _price_stats(rows)
    stats["is_sold"] = 1.0 if rows and all(r.get("is_sold", True) for r in rows) else 0.0
    st.session_state[cache_key] = {"rows": rows, "hint": hint, "stats": stats}
    return rows, hint, stats

"""eBay Browse + sold comps blocks for card detail."""

from __future__ import annotations

from html import escape

import streamlit as st

from currency import money
from i18n import t
from services.ebay_listings import load_ebay_listings, load_ebay_sold_comps
from services.epn import affiliate_ebay_url, epn_configured
from services.live_prices import _ebay_module


def ebay_row_html(
    row: dict,
    *,
    meta: str,
    title_len: int = 100,
    customid: str | None = None,
) -> str:
    """One eBay row: always thumb | copy | price | link so CSS grid stays aligned."""
    title = escape((row.get("title") or "")[:title_len])
    price_txt = (
        escape(money(float(row["price"])))
        if row.get("price") is not None
        else "—"
    )
    url = affiliate_ebay_url(str(row.get("url") or "").strip(), customid=customid)
    img = str(row.get("image") or "").strip()
    if img.startswith("http"):
        thumb = (
            f'<div class="ebay-thumb"><img src="{escape(img, quote=True)}" '
            f'alt="" loading="lazy" referrerpolicy="no-referrer" '
            f'onerror="this.parentElement.style.opacity=\'0.35\'" /></div>'
        )
    else:
        thumb = '<div class="ebay-thumb" aria-hidden="true"></div>'
    rel = "noopener noreferrer sponsored" if epn_configured() else "noopener noreferrer"
    link = (
        f'<a class="ebay-link" href="{escape(url, quote=True)}" '
        f'target="_blank" rel="{rel}">eBay ↗</a>'
        if url.startswith("http")
        else '<span class="ebay-link ebay-link-muted">—</span>'
    )
    return (
        f'<div class="ebay-row">{thumb}'
        f'<div class="ebay-copy"><div class="ebay-title">{title}</div>'
        f'<div class="ebay-meta">{escape(meta)}</div></div>'
        f'<div class="ebay-price">{price_txt}</div>{link}</div>'
    )


def render_detail_ebay_sections(*, card_id: str, card_name: str, set_name: str) -> None:
    """Active listings + sold comps under the detail chart."""
    ebay = _ebay_module()
    st.markdown(
        f"""
        <div class="ebay-block">
          <div class="compare-head">
            <h3>{escape(t("ebay_listings"))}</h3>
            <p class="compare-caption">{escape(t("ebay_listings_caption"))}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not ebay.ebay_configured():
        st.info(t("ebay_key_missing"))
        st.caption(t("ebay_key_missing_hint"))
    else:
        with st.spinner(t("ebay_loading")):
            ebay_rows, ebay_error = load_ebay_listings(
                card_id=str(card_id),
                name=str(card_name),
                set_name=str(set_name or ""),
            )
        if ebay_error:
            st.warning(t("ebay_fetch_error", error=ebay_error[:220]))
        elif not ebay_rows:
            st.info(t("ebay_no_results"))
        else:
            priced = [r for r in ebay_rows if r.get("price") is not None]
            if priced:
                lowest = min(float(r["price"]) for r in priced)
                st.caption(
                    t(
                        "ebay_from_price",
                        price=money(lowest),
                        n=len(ebay_rows),
                    )
                )
            if epn_configured():
                st.caption(t("ebay_epn_disclosure"))
            rows_html = [
                ebay_row_html(
                    r,
                    meta=str(r.get("condition") or "—"),
                    customid=f"detail-active-{card_id}",
                )
                for r in ebay_rows
            ]
            st.markdown(
                f'<div class="ebay-list">{"".join(rows_html)}</div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        f"""
        <div class="ebay-block">
          <div class="compare-head">
            <h3>{escape(t("ebay_sold_title"))}</h3>
            <p class="compare-caption">{escape(t("ebay_sold_caption"))}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not ebay.ebay_configured():
        return
    sold_rows, sold_hint, sold_stats = load_ebay_sold_comps(
        card_id=str(card_id),
        name=str(card_name),
        set_name=str(set_name or ""),
    )
    is_sold_comps = bool(sold_stats.get("is_sold", 1.0))
    if not sold_rows or not is_sold_comps:
        st.info(t("ebay_sold_active_fallback"))
        if not sold_rows and sold_hint and sold_hint not in {"insights_unavailable", None}:
            st.caption(t("ebay_sold_unavailable", hint=str(sold_hint)[:220]))
        elif not sold_rows:
            st.caption(t("ebay_sold_see_active"))
        return
    if sold_stats.get("n"):
        st.caption(
            t(
                "ebay_sold_stats",
                n=int(sold_stats["n"]),
                lo=money(float(sold_stats["min"])) if sold_stats.get("min") is not None else "—",
                mid=money(float(sold_stats["median"])) if sold_stats.get("median") is not None else "—",
                hi=money(float(sold_stats["max"])) if sold_stats.get("max") is not None else "—",
            )
        )
    if epn_configured():
        st.caption(t("ebay_epn_disclosure"))
    sold_html = [
        ebay_row_html(
            r,
            meta=str(r.get("sold_date") or r.get("condition") or "—"),
            title_len=90,
            customid=f"detail-sold-{card_id}",
        )
        for r in sold_rows
    ]
    st.markdown(
        f'<div class="ebay-list">{"".join(sold_html)}</div>',
        unsafe_allow_html=True,
    )

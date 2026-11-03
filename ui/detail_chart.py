"""Compare / live price chart panel for card detail."""

from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from ai_insights import series_confidence
from i18n import t
from services.live_prices import (
    _justtcg_module,
    load_justtcg_series,
    load_psa10_series,
)
from services.prices import clear_live_price_caches, record_justtcg_event
from ui.chart import (
    clip_series_range,
    inject_chart_hover_counter,
    price_chart,
    render_chart_price_counter,
)
from ui.skeletons import render_chart_skeleton


def render_pill_toggle(options, *, state_key: str, default: str) -> str:
    from ui.common import render_pill_toggle as _pill

    return _pill(options, state_key=state_key, default=default)


def render_detail_compare_chart(
    *,
    card_id: str,
    card: Any,
    market_series: pd.DataFrame,
    tcgplayer_id: str | None,
    predicted: float,
) -> str | None:
    """Render source toggles + overlays. Returns possibly updated tcgplayer_id."""
    justtcg_api_key = _justtcg_module().justtcg_api_key

    st.markdown(
        f"""
        <div class="compare-head">
          <h3>{escape(t("compare_history"))}</h3>
          <p class="compare-caption">{escape(t("compare_history_caption"))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    r1, r2 = st.columns([1.1, 1.5])
    with r1:
        st.caption(t("chart_range"))
        range_key = render_pill_toggle(
            [("1m", "1M"), ("3m", "3M"), ("all", t("chart_range_all"))],
            state_key=f"detail_range_{card_id}",
            default="1m",
        )
    with r2:
        st.caption(t("price_source"))
        source_key = render_pill_toggle(
            [
                ("compare", t("chart_compare_all")),
                ("tcgplayer", "TCGplayer"),
                ("justtcg", "JustTCG NM"),
                ("psa10", "PSA 10"),
            ],
            state_key=f"detail_source_{card_id}",
            default="compare" if justtcg_api_key() else "tcgplayer",
        )

    just_series = pd.DataFrame(columns=["date", "price"])
    justtcg_error: str | None = None
    used_db_fallback = False
    psa10_stats: dict = {}
    psa10_error: str | None = None
    psa_series = pd.DataFrame(columns=["date", "price"])
    has_justtcg_key = bool(justtcg_api_key())
    need_just = source_key in {"justtcg", "compare"}
    need_psa = source_key in {"psa10", "compare"}

    if need_just and has_justtcg_key:
        cache_probe = f"justtcg_series::{card_id}::"
        has_cached = any(
            str(k).startswith(cache_probe)
            and isinstance(st.session_state.get(k), pd.DataFrame)
            and not st.session_state.get(k).empty
            for k in st.session_state.keys()
        )
        skel = st.empty()
        if not has_cached:
            with skel.container():
                render_chart_skeleton()
        with st.spinner(t("loading_justtcg")):
            try:
                just_series, resolved_tcp = load_justtcg_series(
                    tcgplayer_id=tcgplayer_id,
                    card_id=str(card_id),
                    name=str(card["name"]),
                    set_name=str(card.get("set_name") or ""),
                )
                if resolved_tcp and not tcgplayer_id:
                    tcgplayer_id = resolved_tcp
            except Exception as exc:
                justtcg_error = str(exc)
                just_series = pd.DataFrame(columns=["date", "price"])
        skel.empty()
        if just_series.empty and not market_series.empty:
            just_series = market_series[["date", "price"]].copy()
            used_db_fallback = True

    if need_psa and has_justtcg_key:
        with st.spinner(t("loading_psa10")):
            try:
                psa_series, resolved_tcp, psa10_stats = load_psa10_series(
                    tcgplayer_id=tcgplayer_id,
                    card_id=str(card_id),
                    name=str(card["name"]),
                    set_name=str(card.get("set_name") or ""),
                )
                if resolved_tcp and not tcgplayer_id:
                    tcgplayer_id = resolved_tcp
            except Exception as exc:
                psa10_error = str(exc)
                psa_series = pd.DataFrame(columns=["date", "price"])
                psa10_stats = {}

    badges: list[str] = []
    overlays: list[tuple[pd.DataFrame, str, str]] = []
    chart_series = pd.DataFrame(columns=["date", "price"])
    source_label = "TCGplayer"
    line_color = "#d07272"
    latest_src: float | None = None
    meta_note = t("source_market_db")
    available = False
    if source_key == "compare":
        db_clip = clip_series_range(market_series, range_key)
        just_clip = clip_series_range(just_series, range_key) if not just_series.empty else just_series
        psa_clip = clip_series_range(psa_series, range_key) if not psa_series.empty else psa_series
        chart_series = just_clip if not just_clip.empty else db_clip
        source_label = t("chart_overlay")
        line_color = "#B87333"
        overlays = []
        if not db_clip.empty:
            overlays.append((db_clip, "TCGplayer", "#d07272"))
            badges.append(f'<span class="source-badge db">{escape(t("badge_db"))}</span>')
        if not just_clip.empty:
            st.session_state[f"_db_fb::{card_id}"] = bool(used_db_fallback)
            if used_db_fallback:
                record_justtcg_event("fallback")
                badges.append(
                    f'<span class="source-badge saved">{escape(t("badge_saved"))}</span>'
                )
            else:
                badges.append(
                    f'<span class="source-badge live">{escape(t("badge_live"))}</span>'
                )
            if chart_series is just_clip:
                source_label = "JustTCG NM"
            else:
                overlays.append((just_clip, "JustTCG NM", "#B87333"))
        if not psa_clip.empty:
            overlays.append((psa_clip, "PSA 10", "#D4A574"))
            has_hist = bool(psa10_stats.get("has_history_series"))
            badges.append(
                f'<span class="source-badge {"spot" if not has_hist else "live"}">'
                f'{escape(t("badge_spot") if not has_hist else "PSA 10")}</span>'
            )
        # Primary already JustTCG — avoid duplicating in overlays when it is primary.
        overlays = [
            (fr, lab, col)
            for fr, lab, col in overlays
            if not (lab == "JustTCG NM" and source_label == "JustTCG NM")
        ]
        available = not chart_series.empty or bool(overlays)
        latest_src = (
            float(chart_series["price"].iloc[-1])
            if not chart_series.empty
            else (
                float(overlays[0][0]["price"].iloc[-1]) if overlays else None
            )
        )
        meta_note = t("chart_overlay")
        if not has_justtcg_key:
            st.info(t("justtcg_key_missing"))
        if justtcg_error:
            st.warning(t("justtcg_fetch_error", error=justtcg_error[:180]))
        if psa10_error:
            st.warning(t("psa10_fetch_error", error=psa10_error[:180]))
    elif source_key == "justtcg":
        chart_series = clip_series_range(just_series, range_key)
        source_label = "JustTCG NM"
        line_color = "#B87333"
        available = not chart_series.empty
        latest_src = float(chart_series["price"].iloc[-1]) if available else None
        meta_note = (
            t("source_nm_db_fallback") if used_db_fallback else t("source_nm_usd")
        )
        st.session_state[f"_db_fb::{card_id}"] = bool(used_db_fallback)
        badges.append(
            f'<span class="source-badge {"saved" if used_db_fallback else "live"}">'
            f'{escape(t("badge_saved") if used_db_fallback else t("badge_live"))}</span>'
        )
        if not has_justtcg_key:
            st.info(t("justtcg_key_missing"))
        if justtcg_error:
            st.warning(t("justtcg_fetch_error", error=justtcg_error[:180]))
        elif has_justtcg_key and not available:
            st.info(t("source_unavailable"))
        elif used_db_fallback and has_justtcg_key:
            record_justtcg_event("fallback")
            st.caption(t("justtcg_using_saved"))
            st.caption(series_confidence(points=len(market_series), used_db_fallback=True)["reason"])
    elif source_key == "psa10":
        chart_series = clip_series_range(psa_series, range_key)
        source_label = "JustTCG PSA 10"
        line_color = "#D4A574"
        available = not chart_series.empty
        latest_src = float(chart_series["price"].iloc[-1]) if available else None
        has_hist = bool(psa10_stats.get("has_history_series"))
        if has_hist:
            meta_note = t("source_psa10_usd")
            badges.append(f'<span class="source-badge live">PSA 10</span>')
        else:
            meta_note = t(
                "source_psa10_spot_only",
                period=str(psa10_stats.get("period_key") or "—"),
                sales=str(
                    psa10_stats.get("sales_count")
                    if psa10_stats.get("sales_count") is not None
                    else "—"
                ),
            )
            badges.append(
                f'<span class="source-badge spot">{escape(t("badge_spot"))}</span>'
            )
        if not has_justtcg_key:
            st.info(t("justtcg_key_missing"))
        if psa10_error:
            st.warning(t("psa10_fetch_error", error=psa10_error[:180]))
        elif has_justtcg_key and not available:
            st.info(t("psa10_unpriced"))
        elif has_justtcg_key and available and not has_hist:
            st.caption(meta_note)
    else:
        chart_series = clip_series_range(market_series, range_key)
        source_label = "TCGplayer"
        line_color = "#d07272"
        available = not chart_series.empty
        latest_src = float(chart_series["price"].iloc[-1]) if available else None
        meta_note = t("source_market_db")
        badges.append(f'<span class="source-badge db">{escape(t("badge_db"))}</span>')

    if badges:
        st.markdown(
            f'<div class="source-badges">{"".join(badges)}</div>',
            unsafe_allow_html=True,
        )

    counter_id = f"chart-price-{card_id}-{source_key}"
    if latest_src is not None:
        render_chart_price_counter(
            latest_src,
            counter_id=counter_id,
            accent=line_color,
        )
    st.plotly_chart(
        price_chart(
            chart_series if isinstance(chart_series, pd.DataFrame) else pd.DataFrame(),
            predicted if source_key in {"tcgplayer", "compare"} else None,
            str(card["name"]),
            source_label=source_label,
            show_ai=(source_key in {"tcgplayer", "compare"}),
            line_color=line_color,
            overlays=overlays if source_key == "compare" else None,
        ),
        width="stretch",
        key=f"detail_chart_{card_id}_{source_key}_{range_key}",
        config={"displayModeBar": False, "responsive": True},
    )
    if latest_src is not None:
        inject_chart_hover_counter(counter_id)

    pts = len(chart_series) if isinstance(chart_series, pd.DataFrame) else 0
    st.markdown(
        f"""
        <div class="source-card">
          <div class="src-title">{escape(t('source_label', name=source_label))}</div>
          <p class="src-meta">{escape(meta_note)} · {pts} {escape(t('points_series').lower())}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(t("retry_live_prices"), key=f"retry_live_{card_id}"):
        clear_live_price_caches(card_id=str(card_id))
        st.session_state["portfolio_notice"] = t("retry_live_done")
        st.rerun()

    return tcgplayer_id

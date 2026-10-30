"""Card detail panel: multi-source charts, AI explain, eBay."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from ai_insights import explain_features, series_confidence
from currency import currency_code, from_display, money, money_delta, to_display
from database import add_watchlist_card, is_on_watchlist, remove_watchlist_card
from i18n import signal_label, t
from services.forecast import card_history, lag_features_for_last_day, predict_next_close
from services.ebay_listings import load_ebay_listings, load_ebay_sold_comps
from services.live_prices import (
    _ebay_module,
    load_justtcg_series,
    load_psa10_series,
    resolve_tcgplayer_id,
)
from services.prices import clear_live_price_caches, record_justtcg_event
from trading_signals import HOLD_BAND, SIGNAL_CLASS
from ui.chart import (
    clip_series_range,
    inject_chart_hover_counter,
    price_chart,
    render_chart_price_counter,
)
from ui.skeletons import render_chart_skeleton

# Helpers provided by app composition root / ui.common — imported lazily to avoid cycles.


def chip_row(items, css_class: str) -> None:
    from ui.common import chip_row as _chip_row

    return _chip_row(items, css_class)


def render_pill_toggle(options, *, state_key: str, default: str) -> str:
    from ui.common import render_pill_toggle as _pill

    return _pill(options, state_key=state_key, default=default)


def card_image_for_id(card_id: str) -> str:
    from ui.tiles import card_image_for_id as _img

    return _img(card_id)


def _current_user_id() -> str:
    import auth as auth_mod

    user = auth_mod.current_user() or {}
    return str(user.get("id") or "").strip()


def render_market_detail(history: pd.DataFrame, market: pd.DataFrame, model, card_id: str) -> None:
    justtcg_api_key = _justtcg_module().justtcg_api_key

    card = market.loc[market["id"] == card_id].iloc[0]
    tcgplayer_id = resolve_tcgplayer_id(str(card_id))

    market_series = card_history(history, str(card["id"]))
    if market_series.empty:
        st.error(t("no_history_card"))
        return

    # AI uvijek na market/DB seriji (trenutni model).
    last_price = float(market_series["price"].iloc[-1])
    previous_price = (
        float(market_series["price"].iloc[-2]) if len(market_series) > 1 else last_price
    )
    predicted = predict_next_close(
        model,
        market_series,
        float(card["rarity_encoded"]),
        float(card["supertype_encoded"]),
    )
    if predicted is None:
        st.warning(t("short_series"))
        predicted = float(card["predicted_price"])
    change_pct = (predicted - last_price) / last_price * 100.0
    lags = lag_features_for_last_day(market_series) or {
        "price_lag_1": float(card.get("price_lag_1", last_price)),
        "rolling_mean_7": float(card.get("rolling_mean_7", last_price)),
    }
    day_change_pct = (
        (last_price - previous_price) / previous_price * 100.0 if previous_price else 0.0
    )
    signal = trading_signal(last_price, predicted)
    next_day = (pd.Timestamp(market_series["date"].iloc[-1]) + pd.Timedelta(days=1)).strftime(
        "%d.%m.%Y"
    )
    delta_cls = "up" if day_change_pct > 0.05 else "down" if day_change_pct < -0.05 else "flat"
    image = escape(card_image_for_id(str(card["id"])), quote=True)

    # Desktop: ~1/3 karta+AI | ~2/3 compare graf (kao TCG Forecast).
    left, right = st.columns([1.05, 2.15], gap="large")

    with left:
        st.markdown(
            f"""
            <div class="detail-hero">
              <img src="{image}" alt="{escape(str(card['name']))}"
                   onerror="this.style.opacity='0.25';" />
              <div class="detail-hero-copy">
                <div class="detail-hero-title">{escape(str(card['name']))}</div>
                <div class="detail-hero-meta">{escape(str(card['set_name']))} · {escape(str(card['rarity']))} · {escape(str(card['id']))}</div>
                <div class="detail-hero-price">{escape(money(last_price))}</div>
                <div class="detail-hero-delta {delta_cls}">{day_change_pct:+.2f}% · {escape(signal_label(signal))}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        chip_row(
            [
                ("60d min", money(float(market_series["price"].min()), digits=4)),
                ("60d max", money(float(market_series["price"].max()), digits=4)),
            ],
            "stat-row",
        )
        st.markdown(
            f'<div class="detail-ai-head"><h3>{escape(t("ai_prediction"))}</h3></div>',
            unsafe_allow_html=True,
        )
        confidence = series_confidence(points=len(market_series), used_db_fallback=False)
        st.markdown(
            f'<div class="ai-move-label">{escape(t("ai_expected_move"))}</div>'
            f'<div class="ai-move-value">{change_pct:+.2f}%</div>',
            unsafe_allow_html=True,
        )
        st.metric(
            t("price_on", date=next_day),
            money(predicted, digits=4),
            delta=f"{money_delta(predicted - last_price)} ({change_pct:+.2f}%)",
        )
        if confidence["ok"]:
            st.markdown(
                f'<div class="{SIGNAL_CLASS[signal]}">{signal_label(signal)}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info(t("ai_low_confidence"))
        st.caption(t("ai_caption", band=HOLD_BAND * 100))
        explain_rows = explain_features(
            lags=lags,
            last_price=last_price,
            predicted=float(predicted),
            hold_band=HOLD_BAND,
            horizon_days=1,
        )
        explain_html = "".join(
            f"<div><strong>{escape(k)}</strong>: {escape(v)}</div>" for k, v in explain_rows
        )
        st.markdown(
            f'<div class="ai-explain"><div class="ai-conf">'
            f'{escape(t("ai_confidence", level=confidence["level"]))}'
            f" — {escape(str(confidence['reason']))}</div>"
            f"<div><strong>{escape(t('ai_explain_title'))}</strong></div>"
            f"{explain_html}</div>",
            unsafe_allow_html=True,
        )
        try:
            uid = _current_user_id()
            watching = is_on_watchlist(str(card_id), user_id=uid)
            w_label = t("watchlist_remove") if watching else t("watchlist_add")
            if st.button(w_label, key=f"watch_{card_id}", use_container_width=True):
                try:
                    if watching:
                        remove_watchlist_card(str(card_id), user_id=uid)
                        st.session_state["portfolio_notice"] = t("watchlist_removed")
                    else:
                        add_watchlist_card(str(card_id), user_id=uid)
                        st.session_state["portfolio_notice"] = t("watchlist_added")
                except Exception as exc:
                    if "watchlist" in str(exc).lower() or "pgrst" in str(exc).lower():
                        st.warning(t("watchlist_missing_table"))
                    else:
                        st.warning(str(exc)[:180])
                else:
                    st.rerun()
        except Exception:
            pass

    with right:
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
        line_color = "#f87171"
        latest_src: float | None = None
        meta_note = t("source_market_db")
        available = False
        if source_key == "compare":
            db_clip = clip_series_range(market_series, range_key)
            just_clip = clip_series_range(just_series, range_key) if not just_series.empty else just_series
            psa_clip = clip_series_range(psa_series, range_key) if not psa_series.empty else psa_series
            chart_series = just_clip if not just_clip.empty else db_clip
            source_label = t("chart_overlay")
            line_color = "#60a5fa"
            overlays = []
            if not db_clip.empty:
                overlays.append((db_clip, "TCGplayer", "#f87171"))
                badges.append(f'<span class="source-badge db">{escape(t("badge_db"))}</span>')
            if not just_clip.empty:
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
                    overlays.append((just_clip, "JustTCG NM", "#60a5fa"))
            if not psa_clip.empty:
                overlays.append((psa_clip, "PSA 10", "#c4b5fd"))
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
            line_color = "#60a5fa"
            available = not chart_series.empty
            latest_src = float(chart_series["price"].iloc[-1]) if available else None
            meta_note = (
                t("source_nm_db_fallback") if used_db_fallback else t("source_nm_usd")
            )
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
            line_color = "#c4b5fd"
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
            line_color = "#f87171"
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

    # eBay Browse — full-width ispod hero/graf layouta (ne utisnuto u desni stupac).
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
                name=str(card["name"]),
                set_name=str(card.get("set_name") or ""),
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
            rows_html: list[str] = []
            for r in ebay_rows:
                title = escape((r.get("title") or "")[:100])
                condition = escape(str(r.get("condition") or "—"))
                price_txt = (
                    escape(money(float(r["price"])))
                    if r.get("price") is not None
                    else "—"
                )
                url = str(r.get("url") or "").strip()
                img = str(r.get("image") or "").strip()
                if img.startswith("http"):
                    thumb = (
                        f'<div class="ebay-thumb"><img src="{escape(img, quote=True)}" '
                        f'alt="" loading="lazy" referrerpolicy="no-referrer" '
                        f'onerror="this.parentElement.style.opacity=\'0.35\'" /></div>'
                    )
                else:
                    thumb = '<div class="ebay-thumb" aria-hidden="true"></div>'
                link = (
                    f'<a class="ebay-link" href="{escape(url, quote=True)}" '
                    f'target="_blank" rel="noopener noreferrer">eBay ↗</a>'
                    if url.startswith("http")
                    else '<span class="ebay-meta">—</span>'
                )
                rows_html.append(
                    f'<div class="ebay-row">{thumb}'
                    f'<div class="ebay-copy"><div class="ebay-title">{title}</div>'
                    f'<div class="ebay-meta">{condition}</div></div>'
                    f'<div class="ebay-price">{price_txt}</div>'
                    f"{link}</div>"
                )
            st.markdown(
                f'<div class="ebay-list">{"".join(rows_html)}</div>',
                unsafe_allow_html=True,
            )

    # Sold comps (Insights) — soft fallback when gated.
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
    if ebay.ebay_configured():
        sold_rows, sold_hint, sold_stats = load_ebay_sold_comps(
            card_id=str(card_id),
            name=str(card["name"]),
            set_name=str(card.get("set_name") or ""),
        )
        if sold_hint and not sold_rows:
            st.caption(t("ebay_sold_unavailable", hint=sold_hint))
        elif sold_rows:
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
            sold_html = []
            for r in sold_rows:
                title = escape((r.get("title") or "")[:90])
                price_txt = (
                    escape(money(float(r["price"])))
                    if r.get("price") is not None
                    else "—"
                )
                sold_date = escape(str(r.get("sold_date") or "—"))
                sold_html.append(
                    f'<div class="ebay-row"><div class="ebay-copy">'
                    f'<div class="ebay-title">{title}</div>'
                    f'<div class="ebay-meta">{sold_date}</div></div>'
                    f'<div class="ebay-price">{price_txt}</div></div>'
                )
            st.markdown(
                f'<div class="ebay-list">{"".join(sold_html)}</div>',
                unsafe_allow_html=True,
            )


"""Card detail panel: multi-source charts, AI explain, eBay."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from ai_insights import explain_features, series_confidence
from currency import currency_code, from_display, money, money_delta, to_display
from database import (
    add_portfolio_position,
    add_watchlist_card,
    is_on_watchlist,
    remove_watchlist_card,
)
from ai_xgboost import HORIZON_DAYS
from i18n import signal_label, t
from services.forecast import card_history, lag_features_for_last_day, predict_next_close
from services.live_prices import resolve_tcgplayer_id
from trading_signals import FORECAST_SIGNAL_BAND, SIGNAL_CLASS, trading_signal
from ui.detail_chart import render_detail_compare_chart
from ui.detail_ebay import render_detail_ebay_sections


def chip_row(items, css_class: str) -> None:
    from ui.common import chip_row as _chip_row

    return _chip_row(items, css_class)


def card_image_for_id(card_id: str) -> str:
    from ui.tiles import card_image_for_id as _img

    return _img(card_id)


def _current_user_id() -> str:
    import auth as auth_mod

    user = auth_mod.current_user() or {}
    return str(user.get("id") or "").strip()


def _render_add_lot_form(card_id: str, card_name: str, default_price: float) -> None:
    """Compact add-lot controls on the detail panel (signal → portfolio)."""
    conditions = ["NM", "LP", "MP", "HP", "DMG", "PSA 10", "PSA 9", "Other"]
    with st.expander(t("add_lot_detail"), expanded=False):
        st.caption(t("add_lot_detail_caption"))
        with st.form(f"detail_add_lot_{card_id}", clear_on_submit=True):
            qty = st.number_input(t("quantity"), min_value=1, step=1, value=1)
            cost_display = st.number_input(
                t("purchase_price", code=currency_code()),
                min_value=0.0001,
                step=0.01,
                value=float(to_display(max(float(default_price), 0.0001))),
                format="%.4f",
            )
            cond_col, grade_col = st.columns(2)
            condition = cond_col.selectbox(t("condition"), conditions, index=0)
            grade = grade_col.text_input(t("grade"), value="")
            submitted = st.form_submit_button(t("add_to_portfolio"), type="primary")
        if not submitted:
            return
        uid = _current_user_id()
        try:
            add_portfolio_position(
                str(card_id),
                int(qty),
                float(from_display(cost_display)),
                user_id=uid,
                condition=str(condition),
                grade=str(grade).strip() or None,
            )
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            message = str(exc)
            if "user_id" in message.lower():
                st.error(t("portfolio_user_id_migration"))
            else:
                st.error(message[:220])
        else:
            st.success(t("added_to_portfolio", name=card_name))


def render_market_detail(history: pd.DataFrame, market: pd.DataFrame, model, card_id: str) -> None:
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
    rarity_enc = card["rarity_encoded"] if "rarity_encoded" in card.index else None
    supertype_enc = card["supertype_encoded"] if "supertype_encoded" in card.index else None
    predicted = None
    if rarity_enc is not None and supertype_enc is not None and pd.notna(rarity_enc) and pd.notna(supertype_enc):
        try:
            predicted = predict_next_close(
                model,
                market_series,
                float(rarity_enc),
                float(supertype_enc),
            )
        except Exception:
            predicted = None
    if predicted is None:
        st.warning(t("short_series"))
        predicted = float(card["predicted_price"])
    change_pct = (predicted - last_price) / last_price * 100.0
    lags = lag_features_for_last_day(market_series) or {
        "ret_1": 0.0,
        "ret_7": 0.0,
        "vol_7": 0.0,
        "dist_ma_7": 0.0,
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
        used_fb = bool(st.session_state.get(f"_db_fb::{card_id}", False))
        confidence = series_confidence(points=len(market_series), used_db_fallback=used_fb)
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
        conf_board = True
        if hasattr(card, "get"):
            conf_board = bool(card.get("confidence_ok", True))
            if card.get("conformal_ok") is not None and str(card.get("conformal_ok")) != "nan":
                conf_board = conf_board and bool(card.get("conformal_ok"))
        show_signal = bool(confidence["ok"] and conf_board)
        if show_signal:
            st.markdown(
                f'<div class="{SIGNAL_CLASS[signal]}">{signal_label(signal)}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info(t("ai_low_confidence"))
        st.caption(t("ai_caption", band=FORECAST_SIGNAL_BAND * 100))
        lo_pct = card.get("pred_lo_pct") if hasattr(card, "get") else getattr(card, "pred_lo_pct", None)
        hi_pct = card.get("pred_hi_pct") if hasattr(card, "get") else getattr(card, "pred_hi_pct", None)
        try:
            lo_pct = float(lo_pct) if lo_pct is not None else None
            hi_pct = float(hi_pct) if hi_pct is not None else None
        except (TypeError, ValueError):
            lo_pct, hi_pct = None, None
        explain_rows = explain_features(
            lags=lags,
            last_price=last_price,
            predicted=float(predicted),
            hold_band=FORECAST_SIGNAL_BAND,
            horizon_days=int(HORIZON_DAYS),
            pred_lo_pct=lo_pct,
            pred_hi_pct=hi_pct,
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
        from ui.nav import is_logged_in, set_nav_query_params

        if is_logged_in():
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
            _render_add_lot_form(str(card_id), str(card["name"]), last_price)
        else:
            st.caption(t("login_required_watchlist"))
            if st.button(t("login_signin"), key=f"watch_login_{card_id}", use_container_width=True):
                st.session_state["nav_page"] = "login"
                set_nav_query_params(page="login")
                st.rerun()

    with right:
        render_detail_compare_chart(
            card_id=str(card_id),
            card=card,
            market_series=market_series,
            tcgplayer_id=tcgplayer_id,
            predicted=float(predicted),
        )

    render_detail_ebay_sections(
        card_id=str(card_id),
        card_name=str(card["name"]),
        set_name=str(card.get("set_name") or ""),
    )

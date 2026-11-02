"""Dealer desk UI — CSV inventory × fee-aware AI actions."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from currency import money
from i18n import t
from services.dealer_desk import (
    ACTION_BUY_MORE,
    ACTION_HOLD,
    ACTION_LIST,
    DEFAULT_SELL_FEE_PCT,
    DEFAULT_SHIP_USD,
    build_dealer_board,
    parse_inventory_csv,
)
from ui.nav import set_nav_query_params


def _action_label(action: str) -> str:
    key = {
        ACTION_LIST: "desk_action_list",
        ACTION_BUY_MORE: "desk_action_buy",
        ACTION_HOLD: "desk_action_hold",
    }.get(str(action), "desk_action_hold")
    return t(key)


def render_dealer_desk(market: pd.DataFrame) -> None:
    st.subheader(t("desk_title"))
    st.caption(t("desk_caption"))

    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        fee = float(
            st.number_input(
                t("desk_fee_pct"),
                min_value=0.0,
                max_value=35.0,
                value=float(st.session_state.get("desk_fee_pct", DEFAULT_SELL_FEE_PCT)),
                step=0.5,
                key="desk_fee_pct_input",
            )
        )
        st.session_state["desk_fee_pct"] = fee
    with c2:
        ship = float(
            st.number_input(
                t("desk_ship_usd"),
                min_value=0.0,
                max_value=50.0,
                value=float(st.session_state.get("desk_ship_usd", DEFAULT_SHIP_USD)),
                step=0.5,
                key="desk_ship_input",
            )
        )
        st.session_state["desk_ship_usd"] = ship
    with c3:
        st.caption(t("desk_fee_help"))

    uploaded = st.file_uploader(
        t("desk_upload"),
        type=["csv"],
        key="desk_csv_upload",
        help=t("desk_upload_help"),
    )
    sample = (
        "card_id,quantity,cost\n"
        "base1-1,2,40.00\n"
        "sv3pt5-198,1,25.50\n"
    )
    with st.expander(t("desk_sample_title"), expanded=False):
        st.code(sample, language="csv")

    if uploaded is None:
        st.info(t("desk_need_csv"))
        return

    try:
        inventory = parse_inventory_csv(uploaded.getvalue())
    except Exception as exc:
        st.error(t("desk_parse_error", error=str(exc)[:220]))
        return
    if inventory.empty:
        st.warning(t("desk_empty_csv"))
        return

    try:
        board = build_dealer_board(
            inventory, market, fee_pct=fee, ship_usd=ship
        )
    except Exception as exc:
        st.error(str(exc)[:220])
        return

    matched = board.loc[board["matched"] == True] if "matched" in board.columns else board  # noqa: E712
    unmatched_n = int(board.attrs.get("unmatched") or 0)
    actionable = matched.loc[matched["action"].isin([ACTION_LIST, ACTION_BUY_MORE])] if not matched.empty else matched

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(t("desk_kpi_rows"), len(inventory))
    k2.metric(t("desk_kpi_matched"), int(matched.shape[0]))
    k3.metric(t("desk_kpi_actions"), int(actionable.shape[0]))
    inv_val = float(matched["inventory_value"].fillna(0).sum()) if not matched.empty else 0.0
    k4.metric(t("desk_kpi_value"), money(inv_val))
    if unmatched_n:
        st.caption(t("desk_unmatched", n=unmatched_n))

    st.markdown(f"##### {t('desk_actions_title')}")
    if actionable.empty:
        st.info(t("desk_no_actions"))
    else:
        for row in actionable.head(40).itertuples(index=False):
            action = str(row.action)
            tone = "up" if action == ACTION_BUY_MORE else "down"
            lo = getattr(row, "pred_lo_pct", None)
            hi = getattr(row, "pred_hi_pct", None)
            pi = ""
            if lo is not None and hi is not None and lo == lo and hi == hi:
                pi = f" · PI {float(lo):+.1f}%…{float(hi):+.1f}%"
            edge = float(row.net_edge_pct or 0.0)
            exp = float(row.expected_change_pct or 0.0)
            line = (
                f"**{_action_label(action)}** · {escape(str(row.name))} "
                f"(`{escape(str(row.card_id))}`) · qty {int(row.quantity)} · "
                f"spot {money(float(row.spot or 0))} · AI {exp:+.1f}% · "
                f"net edge {edge:+.1f}%{pi}"
            )
            cols = st.columns([6, 1])
            with cols[0]:
                if tone == "up":
                    st.success(line)
                else:
                    st.warning(line)
            with cols[1]:
                if st.button(t("desk_open"), key=f"desk_open_{row.card_id}_{row.quantity}"):
                    st.session_state["market_selected_id"] = str(row.card_id)
                    st.session_state["market_detail_only"] = True
                    st.session_state["nav_page"] = "explore"
                    set_nav_query_params(page="explore", card_id=str(row.card_id))
                    st.rerun()

    with st.expander(t("desk_full_table"), expanded=False):
        show = board.copy()
        if not show.empty:
            show["action"] = show["action"].map(_action_label)
            cols = [
                c
                for c in (
                    "action",
                    "name",
                    "card_id",
                    "quantity",
                    "spot",
                    "expected_change_pct",
                    "net_edge_pct",
                    "conformal_ok",
                    "pred_lo_pct",
                    "pred_hi_pct",
                    "matched",
                )
                if c in show.columns
            ]
            st.dataframe(show[cols], use_container_width=True, hide_index=True)

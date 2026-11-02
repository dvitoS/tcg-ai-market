"""Portfolio page: add/edit lots, watchlist, and composition of gallery + perf."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from api_client import pokemontcg_image_url
from currency import currency_code, from_display, money, money_signed, to_display
from database import (
    add_portfolio_position,
    load_portfolio_lots as fetch_portfolio_lots,
    load_watchlist,
    remove_watchlist_card,
    sell_portfolio_position,
    update_portfolio_position,
)
from i18n import t
from ui.portfolio_gallery import render_portfolio_gallery
from ui.portfolio_perf import (
    portfolio_view,
    render_portfolio_kpis,
    render_portfolio_performance,
    render_week_outlook,
)


def _current_user_id() -> str:
    import auth as auth_mod

    user = auth_mod.current_user() or {}
    return str(user.get("id") or "").strip()


def load_portfolio_lots() -> pd.DataFrame:
    uid = _current_user_id()
    if not uid:
        return pd.DataFrame()
    try:
        from database import ensure_portfolio_user_id_column

        ensure_portfolio_user_id_column()
    except Exception:
        pass
    lots = fetch_portfolio_lots(user_id=uid)
    if lots.empty:
        return lots
    lots["image_url"] = [
        (url if isinstance(url, str) and url.strip() else pokemontcg_image_url(str(card_id)))
        for url, card_id in zip(lots["image_url"], lots["card_id"], strict=True)
    ]
    return lots


def render_watchlist_section(market: pd.DataFrame) -> None:
    st.markdown(f"##### {t('watchlist_title')}")
    uid = _current_user_id()
    c_thr, c_sure = st.columns([1.2, 1.4])
    with c_thr:
        threshold_val = float(
            st.number_input(
                t("alert_threshold"),
                min_value=1.0,
                max_value=50.0,
                value=float(st.session_state.get("watch_alert_threshold", 5.0)),
                step=1.0,
                key="watch_alert_threshold_input",
                help=t("alert_threshold_help"),
            )
        )
    with c_sure:
        sure_only = bool(
            st.toggle(
                t("alert_sure_only"),
                value=bool(st.session_state.get("watch_alert_sure_only", True)),
                key="watch_alert_sure_only_input",
                help=t("alert_sure_only_help"),
            )
        )
    st.session_state["watch_alert_threshold"] = threshold_val
    st.session_state["watch_alert_sure_only"] = sure_only
    try:
        from services.email_alerts import smtp_configured

        if smtp_configured():
            st.caption(t("alert_email_enabled"))
        else:
            st.caption(t("alert_email_optional"))
    except Exception:
        st.caption(t("alert_email_optional"))

    try:
        watch = load_watchlist(user_id=uid)
    except Exception:
        st.caption(t("watchlist_missing_table"))
        return
    if watch.empty:
        st.caption(t("watchlist_empty"))
        return

    try:
        from services.alerts import collect_watchlist_alerts, render_watchlist_digest

        digests = collect_watchlist_alerts(
            market,
            watch,
            threshold_pct=threshold_val,
            dismissed=set(),
            sure_only=sure_only,
        )
        with st.expander(t("alert_digest_title", n=len(digests)), expanded=bool(digests)):
            render_watchlist_digest(
                digests,
                threshold_pct=threshold_val,
                money_fmt=money,
                sure_only=sure_only,
            )
    except Exception:
        pass

    quotes = market.set_index("id") if "id" in market.columns else None
    for row in watch.itertuples(index=False):
        c1, c2, c3 = st.columns([3.2, 1.6, 1])
        with c1:
            st.markdown(f"**{escape(str(row.name or row.card_id))}** · `{escape(str(row.card_id))}`")
        with c2:
            price = row.market_price
            delta_txt = ""
            if quotes is not None and str(row.card_id) in quotes.index:
                q = quotes.loc[str(row.card_id)]
                if isinstance(q, pd.DataFrame):
                    q = q.iloc[0]
                price = q.get("price", price) if hasattr(q, "get") else getattr(q, "price", price)
                exp = None
                if hasattr(q, "get"):
                    exp = q.get("expected_change_pct")
                else:
                    exp = getattr(q, "expected_change_pct", None)
                if exp is not None and pd.notna(exp):
                    delta_txt = " · " + t("watchlist_delta", pct=float(exp))
            st.caption(
                (money(float(price)) if price is not None else "—") + delta_txt
            )
        with c3:
            if st.button(t("watchlist_remove"), key=f"wl_rm_{row.card_id}"):
                remove_watchlist_card(str(row.card_id), user_id=uid)
                st.rerun()


def render_portfolio(history: pd.DataFrame, market: pd.DataFrame, model) -> None:
    st.subheader(t("add_card"))
    labels = {
        row.id: f"{row.name}  ·  {row.id}  ·  {money(float(row.price))}"
        for row in market.sort_values("name").itertuples(index=False)
    }
    conditions = ["NM", "LP", "MP", "HP", "DMG", "PSA 10", "PSA 9", "Other"]
    with st.form("add_portfolio", clear_on_submit=True):
        picked, quantity, purchase_price = st.columns([2, 1, 1])
        card_id = picked.selectbox(
            t("card"),
            options=list(labels.keys()),
            format_func=lambda item: labels[item],
        )
        qty = quantity.number_input(t("quantity"), min_value=1, step=1, value=1)
        cost_display = purchase_price.number_input(
            t("purchase_price", code=currency_code()),
            min_value=0.0001,
            step=0.01,
            value=float(to_display(0.10)),
            format="%.4f",
        )
        cond_col, grade_col = st.columns(2)
        condition = cond_col.selectbox(t("condition"), conditions, index=0)
        grade = grade_col.text_input(t("grade"), value="")
        submitted = st.form_submit_button(t("add_to_portfolio"), type="primary")

    if submitted:
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
                st.code(
                    "alter table public.portfolio "
                    "add column if not exists user_id uuid "
                    "references auth.users (id) on delete cascade;\n"
                    "create index if not exists portfolio_user_id_idx "
                    "on public.portfolio (user_id);\n"
                    "notify pgrst, 'reload schema';",
                    language="sql",
                )
            else:
                st.error(message[:220])
        else:
            name = str(market.loc[market["id"] == card_id, "name"].iloc[0])
            st.session_state["portfolio_notice"] = t("added_to_portfolio", name=name)
            st.rerun()

    notice = st.session_state.pop("portfolio_notice", None)
    if notice:
        st.success(notice)

    render_watchlist_section(market)

    try:
        lots = load_portfolio_lots()
    except Exception as exc:
        message = str(exc)
        if "user_id" in message.lower():
            st.error(t("portfolio_user_id_migration"))
            st.code(
                "alter table public.portfolio "
                "add column if not exists user_id uuid "
                "references auth.users (id) on delete cascade;\n"
                "create index if not exists portfolio_user_id_idx "
                "on public.portfolio (user_id);\n"
                "notify pgrst, 'reload schema';",
                language="sql",
            )
            return
        raise
    if lots.empty:
        render_portfolio_kpis(0.0, 0.0, 0.0, 0.0)
        st.info(t("portfolio_empty"))
        return

    if "status" not in lots.columns:
        lots["status"] = "open"
    open_lots = lots.loc[lots["status"].astype(str).str.lower() != "sold"].copy()
    sold_lots = lots.loc[lots["status"].astype(str).str.lower() == "sold"].copy()

    view = portfolio_view(open_lots if not open_lots.empty else lots.iloc[0:0], market, history, model)
    value = float(view["market_value"].sum()) if not view.empty else 0.0
    invested = float(view["invested"].sum()) if not view.empty else 0.0
    pnl = float(view["pnl"].sum()) if not view.empty else 0.0
    pnl_pct = pnl / invested * 100.0 if invested else 0.0
    realized = 0.0
    if not sold_lots.empty:
        for row in sold_lots.itertuples(index=False):
            sale = float(row.sale_price or 0.0)
            cost = float(row.purchase_price or 0.0) * float(row.quantity or 0)
            realized += sale * float(row.quantity or 0) - cost
    render_portfolio_kpis(value, invested, pnl, pnl_pct)
    st.markdown(
        f'<div class="chip"><div class="chip-label">{escape(t("kpi_realized"))}</div>'
        f'<div class="chip-value {"pnl-up" if realized >= 0 else "pnl-down"}">'
        f"{escape(money_signed(realized))}</div></div>",
        unsafe_allow_html=True,
    )
    if not view.empty:
        render_week_outlook(value, float(view["week_value"].sum()))
        render_portfolio_performance(view, lots=lots, history=history)
        render_portfolio_gallery(view)

    # Edit / sell open lots
    if not open_lots.empty:
        st.markdown(f"##### {t('edit_lot')}")
        lot_labels = {
            int(r.id): f"#{r.id} · {r.name} · qty {r.quantity} · {r.condition or 'NM'}"
            for r in open_lots.itertuples(index=False)
        }
        edit_id = st.selectbox(
            t("card"),
            options=list(lot_labels.keys()),
            format_func=lambda i: lot_labels[i],
            key="edit_lot_pick",
        )
        row = open_lots.loc[open_lots["id"] == edit_id].iloc[0]
        uid = _current_user_id()
        with st.form("edit_portfolio_lot"):
            e1, e2, e3 = st.columns(3)
            new_qty = e1.number_input(t("quantity"), min_value=1, value=int(row["quantity"]))
            new_cost = e2.number_input(
                t("purchase_price", code=currency_code()),
                min_value=0.0001,
                value=float(to_display(float(row["purchase_price"]))),
                format="%.4f",
            )
            new_cond = e3.selectbox(
                t("condition"),
                conditions,
                index=conditions.index(str(row.get("condition") or "NM"))
                if str(row.get("condition") or "NM") in conditions
                else 0,
            )
            save = st.form_submit_button(t("save_lot"))
        if save:
            try:
                update_portfolio_position(
                    int(edit_id),
                    user_id=uid,
                    quantity=int(new_qty),
                    purchase_price=float(from_display(new_cost)),
                    condition=str(new_cond),
                )
                st.session_state["portfolio_notice"] = t("lot_updated")
                st.rerun()
            except Exception as exc:
                st.warning(str(exc)[:200])
        with st.form("sell_portfolio_lot"):
            sell_price = st.number_input(
                t("sale_price", code=currency_code()),
                min_value=0.0001,
                value=float(to_display(float(row.get("market_price") or row["purchase_price"]))),
                format="%.4f",
            )
            sell = st.form_submit_button(t("sell_lot"))
        if sell:
            try:
                sell_portfolio_position(
                    int(edit_id),
                    user_id=uid,
                    sale_price=float(from_display(sell_price)),
                )
                st.session_state["portfolio_notice"] = t("lot_sold")
                st.rerun()
            except Exception as exc:
                st.warning(str(exc)[:200])

    if not sold_lots.empty:
        st.markdown(f"##### {t('sold_lots')}")
        st.dataframe(
            sold_lots[
                [
                    c
                    for c in [
                        "name",
                        "quantity",
                        "purchase_price",
                        "sale_price",
                        "sale_date",
                        "condition",
                    ]
                    if c in sold_lots.columns
                ]
            ],
            hide_index=True,
            width="stretch",
        )

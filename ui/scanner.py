"""AI Scanner page: forecast scan, filters, backtest expander."""

from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from ai_insights import backtest_summary, scanner_backtest
from currency import number_format_pattern, to_display
from i18n import FILTER_ALL, FILTER_ALL_SETS, t
from services.forecast import forecast_price_in_days
from trading_signals import FORECAST_DAYS, SCANNER_GROWTH_FLOOR
from ui.common import apply_price_range, paginate_frame, render_market_grid, render_pager, render_price_slider


def _frame_fingerprint(history: pd.DataFrame, market: pd.DataFrame) -> str:
    h_n = len(history)
    m_n = len(market)
    h_tail = ""
    m_tail = ""
    if h_n and "date" in history.columns:
        h_tail = str(history["date"].iloc[-1])
    if m_n and "id" in market.columns:
        m_tail = str(market["id"].iloc[0])
    raw = f"{h_n}|{m_n}|{h_tail}|{m_tail}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


@st.cache_data(show_spinner=False, ttl=30 * 60)
def build_ai_scan(
    history: pd.DataFrame,
    market: pd.DataFrame,
    _model,
    _fingerprint: str,
) -> pd.DataFrame:
    """Za svaku kartu: lagovi → XGBoost → cijena za 7 dana i ROI."""
    del _fingerprint  # cache key only
    rows: list[dict] = []
    for card in market.itertuples(index=False):
        series = (
            history.loc[history["card_id"] == card.id]
            .sort_values("date")
            .reset_index(drop=True)
        )
        if series.empty:
            continue
        current = float(series["price"].iloc[-1])
        if current <= 0:
            continue
        week_price = forecast_price_in_days(
            _model,
            series,
            float(card.rarity_encoded),
            float(card.supertype_encoded),
        )
        if week_price is None:
            continue
        target = float(week_price)
        rows.append(
            {
                "Name": str(card.name),
                "Set": str(card.set_name),
                "Current price": current,
                "AI target price": target,
                "Expected ROI (%)": (target - current) / current * 100.0,
                "id": str(card.id),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=["Name", "Set", "Current price", "AI target price", "Expected ROI (%)", "id"]
        )
    return pd.DataFrame(rows).sort_values("Expected ROI (%)", ascending=False).reset_index(drop=True)


def scanner_table(frame: pd.DataFrame, height: int = 320) -> None:
    cols = [
        c
        for c in ["Name", "Set", "Rarity", "Current price", "AI target price", "Expected ROI (%)"]
        if c in frame.columns
    ]
    display = frame[cols].copy()
    for price_col in ("Current price", "AI target price"):
        if price_col in display.columns:
            display[price_col] = pd.to_numeric(display[price_col], errors="coerce").map(to_display)
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        height=height,
        column_config={
            "Name": st.column_config.TextColumn(t("col_name"), width="medium"),
            "Set": st.column_config.TextColumn(t("set"), width="medium"),
            "Rarity": st.column_config.TextColumn(t("rarity"), width="small"),
            "Current price": st.column_config.NumberColumn(
                t("col_current"),
                format=number_format_pattern(digits=4),
            ),
            "AI target price": st.column_config.NumberColumn(
                t("col_ai_target"),
                format=number_format_pattern(digits=4),
            ),
            "Expected ROI (%)": st.column_config.NumberColumn(t("col_roi"), format="%+.2f%%"),
        },
    )


def _scanner_page_block(prefix: str, frame: pd.DataFrame, page_size: int) -> None:
    if frame.empty:
        return
    fp_key = f"{prefix}_fp"
    fingerprint = f"{len(frame)}|{page_size}|{frame.iloc[0]['id'] if 'id' in frame.columns else ''}"
    if st.session_state.get(fp_key) != fingerprint:
        st.session_state[fp_key] = fingerprint
        st.session_state[f"{prefix}_page"] = 1

    page = int(st.session_state.get(f"{prefix}_page", 1))
    page_rows, page, pages = paginate_frame(frame, page, page_size)
    st.session_state[f"{prefix}_page"] = page
    render_pager(prefix, page, pages, len(frame), page_size)

    grid = page_rows.rename(
        columns={
            "id": "id",
            "Name": "name",
            "Set": "set_name",
            "Rarity": "rarity",
            "Current price": "price",
            "Expected ROI (%)": "expected_change_pct",
        }
    )
    render_market_grid(grid, cols_per_row=6)
    with st.expander(t("table_page"), expanded=False):
        scanner_table(page_rows, height=min(360, 48 + 36 * len(page_rows)))


def render_scanner(history: pd.DataFrame, market: pd.DataFrame, model) -> None:
    st.subheader(t("scanner_title"))
    st.caption(t("scanner_caption", days=FORECAST_DAYS))

    with st.expander(t("backtest_title", days=FORECAST_DAYS), expanded=False):
        st.caption(t("backtest_caption", pct=SCANNER_GROWTH_FLOOR, days=FORECAST_DAYS))
        bt = scanner_backtest(
            history,
            lookback_days=FORECAST_DAYS,
            forward_days=FORECAST_DAYS,
            growth_floor=float(SCANNER_GROWTH_FLOOR),
            top_n=15,
        )
        if bt.empty:
            st.info(t("backtest_empty"))
        else:
            summary = backtest_summary(bt)
            b1, b2, b3 = st.columns(3)
            b1.metric(t("backtest_hit_rate"), f"{summary['hit_rate']:.0f}%")
            b2.metric(t("backtest_avg"), f"{summary['avg_return']:+.1f}%")
            b3.metric(t("cards"), int(summary["n"]))
            show = bt.rename(
                columns={
                    "name": t("col_name"),
                    "trailing_pct": t("backtest_trailing"),
                    "forward_pct": t("backtest_forward"),
                    "anchor_price": t("col_current"),
                    "end_price": t("col_ai_target"),
                }
            )
            cols = [
                c
                for c in [
                    t("col_name"),
                    "set_name",
                    t("backtest_trailing"),
                    t("backtest_forward"),
                    t("col_current"),
                    t("col_ai_target"),
                ]
                if c in show.columns
            ]
            st.dataframe(show[cols], hide_index=True, width="stretch")

    f1, f2, f3, f4, f5 = st.columns([1.4, 1.2, 1, 1, 0.9])
    query = f1.text_input(t("search"), placeholder=t("search_ph_name"), key="scanner_query")
    sets = [FILTER_ALL_SETS] + sorted(market["set_name"].dropna().unique().tolist())
    set_filter = f2.selectbox(
        t("set"),
        sets,
        format_func=lambda s: t("all_sets") if s == FILTER_ALL_SETS else s,
        key="scanner_set",
    )
    rarities = [FILTER_ALL] + sorted(market["rarity"].dropna().unique().tolist())
    rarity_filter = f3.selectbox(
        t("rarity"),
        rarities,
        format_func=lambda r: t("all") if r == FILTER_ALL else r,
        key="scanner_rarity",
    )
    min_growth = f4.number_input(
        t("min_growth_top"),
        min_value=0.0,
        max_value=100.0,
        value=float(SCANNER_GROWTH_FLOOR),
        step=1.0,
        key="scanner_min_growth",
    )
    page_size = int(f5.selectbox(t("per_page"), [12, 24, 48], index=1, key="scanner_page_size"))
    price_min, price_max = render_price_slider("scanner_price", market["price"])

    with st.spinner(t("scanning")):
        scan = build_ai_scan(
            history,
            market,
            model,
            _frame_fingerprint(history, market),
        )

    if scan.empty:
        st.warning(t("no_scan_history"))
        return

    if "Rarity" not in scan.columns and "rarity" in market.columns:
        scan = scan.merge(
            market[["id", "rarity"]].rename(columns={"rarity": "Rarity"}),
            on="id",
            how="left",
        )

    scoped = scan
    if set_filter != FILTER_ALL_SETS:
        scoped = scoped.loc[scoped["Set"] == set_filter]
    if rarity_filter != FILTER_ALL and "Rarity" in scoped.columns:
        scoped = scoped.loc[scoped["Rarity"] == rarity_filter]
    if query.strip():
        q = query.strip()
        scoped = scoped.loc[scoped["Name"].astype(str).str.contains(q, case=False, na=False)]
    scoped = apply_price_range(scoped, "Current price", price_min, price_max)

    if scoped.empty:
        st.warning(t("no_cards_filters"))
        return

    opportunities = (
        scoped.loc[scoped["Expected ROI (%)"] >= float(min_growth)]
        .sort_values("Expected ROI (%)", ascending=False)
        .reset_index(drop=True)
    )
    warnings_df = (
        scoped.loc[scoped["Expected ROI (%)"] < 0]
        .sort_values("Expected ROI (%)", ascending=True)
        .reset_index(drop=True)
    )

    k1, k2, k3 = st.columns(3)
    k1.metric(t("scanned_filtered"), len(scoped))
    k2.metric(t("top_opps"), len(opportunities), delta=f"≥ {min_growth:.0f}%")
    k3.metric(t("drop_warnings"), len(warnings_df))

    st.markdown(
        f'<div class="scanner-title">{t("top_opps_heading", pct=min_growth)}</div>',
        unsafe_allow_html=True,
    )
    if opportunities.empty:
        st.info(t("no_top_opps", pct=min_growth))
    else:
        _scanner_page_block("scan_top", opportunities, page_size)

    st.markdown(
        f'<div class="scanner-title">{t("drop_heading")}</div>',
        unsafe_allow_html=True,
    )
    if warnings_df.empty:
        st.success(t("no_drop_warnings"))
    else:
        _scanner_page_block("scan_warn", warnings_df, page_size)

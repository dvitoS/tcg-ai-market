"""Portfolio valuation, KPIs, outlook, and performance charts."""

from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from currency import currency_symbol, money, money_signed, to_display
from i18n import t
from services.portfolio_outlook import enrich_portfolio_outlook
from trading_signals import PORTFOLIO_HORIZON_DAYS

def portfolio_view(lots: pd.DataFrame, market: pd.DataFrame, history: pd.DataFrame, model) -> pd.DataFrame:
    """Spaja nabave sa spotom i portfolio-native 30d (fallback 7d) outlookom."""
    quote_cols = ["id", "price", "rarity_encoded", "supertype_encoded"]
    if "rarity" in market.columns and "rarity" not in lots.columns:
        quote_cols.append("rarity")
    quotes = market[quote_cols].rename(columns={"id": "card_id"})
    view = lots.merge(quotes, on="card_id", how="left", suffixes=("", "_mkt"))
    if "rarity_mkt" in view.columns:
        view["rarity"] = view["rarity"].fillna(view["rarity_mkt"])
        view = view.drop(columns=["rarity_mkt"])
    view["current_price"] = view["price"].fillna(view["market_price"]).astype(float)
    view["invested"] = view["quantity"] * view["purchase_price"]
    view["market_value"] = view["quantity"] * view["current_price"]
    view["pnl"] = view["market_value"] - view["invested"]
    view["pnl_pct"] = np.where(view["invested"] > 0, view["pnl"] / view["invested"] * 100.0, 0.0)

    view, outlook_info = enrich_portfolio_outlook(
        view, history, fallback_model=model
    )
    # Stash for caption rendering in the same Streamlit run.
    st.session_state["_portfolio_outlook_info"] = outlook_info
    return view

def render_portfolio_kpis(value: float, invested: float, pnl: float, pnl_pct: float) -> None:
    tone = "pnl-up" if pnl > 0 else "pnl-down" if pnl < 0 else ""
    pnl_text = f"{money_signed(pnl)} / {pnl_pct:+.1f}%"
    cells = [
        (t("kpi_value"), money(value), ""),
        (t("kpi_invested"), money(invested), ""),
        (t("kpi_pnl"), pnl_text, tone),
    ]
    html = "".join(
        f'<div class="chip"><div class="chip-label">{escape(label)}</div>'
        f'<div class="chip-value {css}">{escape(text)}</div></div>'
        for label, text, css in cells
    )
    st.markdown(f'<div class="stat-row">{html}</div>', unsafe_allow_html=True)

def render_week_outlook(current_value: float, week_value: float) -> None:
    """Portfolio horizon outlook (30d preferred; caption reflects active model)."""
    if current_value <= 0:
        return
    info = st.session_state.get("_portfolio_outlook_info") or {}
    days = int(info.get("horizon_days") or PORTFOLIO_HORIZON_DAYS)
    using_30d = bool(info.get("using_30d"))
    change_pct = (week_value - current_value) / current_value * 100.0
    if change_pct > 0.05:
        tone = "up"
        sentence = t("outlook_up", pct=change_pct, days=days)
    elif change_pct < -0.05:
        tone = "down"
        sentence = t("outlook_down", pct=abs(change_pct), days=days)
    else:
        tone = "flat"
        sentence = t("outlook_flat", days=days)
    st.markdown(f'<div class="ai-outlook {tone}">{escape(sentence)}</div>', unsafe_allow_html=True)
    caption_key = "outlook_caption_30d" if using_30d else "outlook_caption_fallback"
    st.caption(
        t(
            caption_key,
            current=money(current_value),
            week=money(week_value),
            days=days,
        )
    )


def _parse_lot_date(value) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).normalize()


def portfolio_timeseries(
    lots: pd.DataFrame,
    history: pd.DataFrame,
    *,
    max_days: int = 120,
) -> pd.DataFrame:
    """Daily invested cost basis vs mark-to-market value for held lots."""
    if lots is None or lots.empty or history is None or history.empty:
        return pd.DataFrame(columns=["date", "invested", "market_value"])

    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
    hist = hist.dropna(subset=["date", "card_id", "price"])
    hist["card_id"] = hist["card_id"].astype(str)
    hist["price"] = pd.to_numeric(hist["price"], errors="coerce")
    hist = hist.dropna(subset=["price"])
    if hist.empty:
        return pd.DataFrame(columns=["date", "invested", "market_value"])

    price_wide = (
        hist.sort_values("date")
        .pivot_table(index="date", columns="card_id", values="price", aggfunc="last")
        .sort_index()
        .ffill()
    )

    lot_rows: list[dict] = []
    for row in lots.itertuples(index=False):
        start = _parse_lot_date(getattr(row, "purchase_date", None))
        if start is None:
            continue
        status = str(getattr(row, "status", "open") or "open").lower()
        end = _parse_lot_date(getattr(row, "sale_date", None)) if status == "sold" else None
        if status == "sold" and end is None:
            continue
        lot_rows.append(
            {
                "card_id": str(row.card_id),
                "qty": float(row.quantity or 0),
                "cost": float(row.purchase_price or 0),
                "start": start,
                "end": end,
            }
        )
    if not lot_rows:
        return pd.DataFrame(columns=["date", "invested", "market_value"])

    start_date = min(r["start"] for r in lot_rows)
    end_date = pd.Timestamp.today().normalize()
    # Align to available history window.
    hist_start = pd.Timestamp(price_wide.index.min()).normalize()
    hist_end = pd.Timestamp(price_wide.index.max()).normalize()
    start_date = max(start_date, hist_start)
    end_date = min(end_date, hist_end)
    if end_date < start_date:
        return pd.DataFrame(columns=["date", "invested", "market_value"])

    all_days = pd.date_range(start_date, end_date, freq="D")
    if len(all_days) > max_days:
        all_days = all_days[-max_days:]

    # Reindex prices onto daily calendar.
    price_daily = price_wide.reindex(price_wide.index.union(all_days)).sort_index().ffill()
    price_daily = price_daily.reindex(all_days)

    invested_vals: list[float] = []
    value_vals: list[float] = []
    for day in all_days:
        invested = 0.0
        value = 0.0
        for lot in lot_rows:
            if lot["start"] > day:
                continue
            if lot["end"] is not None and day > lot["end"]:
                continue
            invested += lot["qty"] * lot["cost"]
            px = price_daily.at[day, lot["card_id"]] if lot["card_id"] in price_daily.columns else np.nan
            if px is not None and not pd.isna(px):
                value += lot["qty"] * float(px)
            else:
                value += lot["qty"] * lot["cost"]
        invested_vals.append(invested)
        value_vals.append(value)

    return pd.DataFrame(
        {
            "date": all_days,
            "invested": invested_vals,
            "market_value": value_vals,
        }
    )


def render_portfolio_performance(
    view: pd.DataFrame,
    *,
    lots: pd.DataFrame | None = None,
    history: pd.DataFrame | None = None,
) -> None:
    """Time-series value vs cost, plus snapshot bars for open lots."""
    st.markdown(f"##### {t('portfolio_perf')}")

    series = portfolio_timeseries(lots if lots is not None else view, history if history is not None else pd.DataFrame())
    if not series.empty and len(series) >= 2:
        st.caption(t("portfolio_perf_time"))
        fig_ts = go.Figure()
        fig_ts.add_trace(
            go.Scatter(
                name=t("kpi_invested"),
                x=series["date"],
                y=series["invested"].map(to_display),
                mode="lines",
                line=dict(color="#64748b", width=2),
            )
        )
        fig_ts.add_trace(
            go.Scatter(
                name=t("kpi_value"),
                x=series["date"],
                y=series["market_value"].map(to_display),
                mode="lines",
                line=dict(color="#38bdf8", width=2.5),
                fill="tonexty",
                fillcolor="rgba(56,189,248,0.12)",
            )
        )
        fig_ts.update_layout(
            template="plotly_dark",
            height=300,
            margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(11,18,32,0.35)",
            legend=dict(orientation="h", y=1.12),
            yaxis=dict(tickprefix=currency_symbol()),
            xaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig_ts, width="stretch", config={"displayModeBar": False})

    open_view = view
    if "status" in view.columns:
        open_view = view.loc[view["status"].astype(str).str.lower() != "sold"]
    if open_view.empty:
        return
    with st.expander(t("portfolio_perf_bars"), expanded=False):
        fig = go.Figure()
        names = open_view["name"].astype(str).tolist()
        fig.add_trace(
            go.Bar(
                name=t("kpi_invested"),
                x=names,
                y=open_view["invested"].astype(float).map(to_display),
                marker_color="#64748b",
            )
        )
        fig.add_trace(
            go.Bar(
                name=t("kpi_value"),
                x=names,
                y=open_view["market_value"].astype(float).map(to_display),
                marker_color="#38bdf8",
            )
        )
        fig.update_layout(
            template="plotly_dark",
            barmode="group",
            height=320,
            margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(11,18,32,0.35)",
            legend=dict(orientation="h", y=1.12),
            yaxis=dict(tickprefix=currency_symbol()),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

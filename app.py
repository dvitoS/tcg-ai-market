# pip install streamlit plotly
"""TCG AI Market Dashboard — stvarna povijest cijena i XGBoost."""

from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ai_xgboost import (
    add_time_features,
    card_forecasts,
    drop_incomplete_rows,
    load_history,
    split_features,
    train_xgboost,
)

st.set_page_config(
    page_title="TCG AI Market Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Promjena unutar ovog pojasa ostaje DRŽI; izvan njega je KUPI ili PRODAJ.
HOLD_BAND = 0.0035
SIGNAL_CLASS = {"KUPI": "signal-buy", "PRODAJ": "signal-sell", "DRŽI": "signal-hold"}

CUSTOM_CSS = """
<style>
    .stApp { background: radial-gradient(circle at top left, #132238 0%, #0b1220 45%, #070b14 100%); }
    h1, h2, h3, p, label, span, div { color: #e8eef8 !important; }
    [data-testid="stSidebar"] { background: #0d1626; border-right: 1px solid #1f334d; }
    [data-testid="stMetric"] {
        background: #132033;
        border: 1px solid #24364d;
        border-radius: 14px;
        padding: 12px 16px;
    }
    .signal-buy, .signal-sell, .signal-hold {
        font-size: 1.55rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-align: center;
        padding: 18px;
        border-radius: 14px;
    }
    .signal-buy {
        background: linear-gradient(90deg, #14532d, #166534);
        border: 1px solid #22c55e;
        color: #dcfce7 !important;
    }
    .signal-sell {
        background: linear-gradient(90deg, #7f1d1d, #991b1b);
        border: 1px solid #f87171;
        color: #fee2e2 !important;
    }
    .signal-hold {
        background: linear-gradient(90deg, #78350f, #92400e);
        border: 1px solid #fbbf24;
        color: #fef3c7 !important;
    }
    .detail-row, .stat-row {
        display: grid;
        gap: 12px;
        margin-bottom: 8px;
    }
    .detail-row { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .stat-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .chip {
        background: #132033;
        border: 1px solid #24364d;
        border-radius: 14px;
        padding: 12px 16px;
        min-width: 0;
    }
    .chip-label { font-size: 0.8rem; opacity: 0.72; margin-bottom: 4px; }
    .chip-value { font-size: 1.05rem; font-weight: 650; line-height: 1.3; }
    @media (max-width: 1100px) {
        .detail-row, .stat-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
</style>
"""


def trading_signal(current_price: float, predicted_price: float) -> str:
    change = (predicted_price - current_price) / current_price
    if change > HOLD_BAND:
        return "KUPI"
    if change < -HOLD_BAND:
        return "PRODAJ"
    return "DRŽI"


def assign_signals(quotes: pd.DataFrame) -> pd.DataFrame:
    board = quotes.copy()
    board["expected_change_pct"] = (board["predicted_price"] - board["price"]) / board["price"] * 100.0
    board["signal"] = [
        trading_signal(float(current), float(predicted))
        for current, predicted in zip(board["price"], board["predicted_price"], strict=True)
    ]
    return board


@st.cache_resource(show_spinner="Učitavam povijest i treniram XGBoost...")
def load_exchange() -> tuple[pd.DataFrame, pd.DataFrame]:
    history = load_history()
    featured, _encoders = add_time_features(history)
    trainable = drop_incomplete_rows(featured)
    X_train, _X_test, y_train, _y_test = split_features(trainable)
    model = train_xgboost(X_train, y_train)
    quotes = assign_signals(card_forecasts(model, featured))
    return history, quotes.sort_values("name").reset_index(drop=True)


def card_history(history: pd.DataFrame, card_id: str) -> pd.DataFrame:
    series = history.loc[history["card_id"] == card_id].sort_values("date")
    return series.reset_index(drop=True)


def price_chart(series: pd.DataFrame, predicted: float, name: str) -> go.Figure:
    last_day = pd.Timestamp(series["date"].iloc[-1])
    next_day = last_day + pd.Timedelta(days=1)
    last_price = float(series["price"].iloc[-1])
    signal = trading_signal(last_price, predicted)
    price_low = min(float(series["price"].min()), predicted, last_price)
    price_high = max(float(series["price"].max()), predicted, last_price)
    pad = max((price_high - price_low) * 0.18, price_low * 0.01)
    forecast_color = {"KUPI": "#22c55e", "PRODAJ": "#f87171", "DRŽI": "#fbbf24"}[signal]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=series["date"],
            y=series["price"],
            mode="lines",
            name="Zatvaranje",
            line=dict(color="#38bdf8", width=2.4),
            hovertemplate="%{x|%d.%m.%Y}<br>$%{y:.4f}<extra>Zatvaranje</extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[last_day, next_day],
            y=[last_price, predicted],
            mode="lines+markers",
            name="AI — sljedeći dan",
            line=dict(color=forecast_color, width=2.5, dash="dash"),
            marker=dict(size=9, symbol="diamond", color=forecast_color),
            hovertemplate="%{x|%d.%m.%Y}<br>$%{y:.4f}<extra>AI</extra>",
        )
    )
    fig.update_layout(
        template="plotly_dark",
        title=f"{name} · povijest cijene",
        xaxis_title="Datum",
        yaxis_title="Cijena (USD)",
        height=480,
        margin=dict(l=16, r=16, t=64, b=16),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(11,18,32,0.65)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        xaxis=dict(
            rangeslider=dict(visible=True, bgcolor="#0d1626", thickness=0.06),
            gridcolor="#1e293b",
            showgrid=True,
        ),
        yaxis=dict(
            gridcolor="#1e293b",
            showgrid=True,
            tickprefix="$",
            range=[price_low - pad, price_high + pad],
        ),
    )
    return fig


def chip_row(items: list[tuple[str, str]], css_class: str) -> None:
    cells = "".join(
        f'<div class="chip"><div class="chip-label">{escape(label)}</div>'
        f'<div class="chip-value">{escape(value)}</div></div>'
        for label, value in items
    )
    st.markdown(f'<div class="{css_class}">{cells}</div>', unsafe_allow_html=True)


def main() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.title("📈 TCG AI Market Dashboard")
    st.caption("Pokémon TCG burza · price_history · XGBoost predikcija sljedećeg dana")

    history, market = load_exchange()
    if market.empty or history.empty:
        st.error("Nema povijesti cijena. Pokreni `python generate_history.py`.")
        return

    st.sidebar.header("Tražilica karata")
    query = st.sidebar.text_input("Pretraži po imenu", placeholder="npr. Pikachu, Charizard...")
    rarities = ["Sve"] + sorted(market["rarity"].dropna().unique().tolist())
    rarity_filter = st.sidebar.selectbox("Rijetkost", rarities)
    signal_filter = st.sidebar.selectbox("Signal", ["Sve", "KUPI", "PRODAJ", "DRŽI"])

    filtered = market
    if query.strip():
        filtered = filtered[filtered["name"].str.contains(query.strip(), case=False, na=False)]
    if rarity_filter != "Sve":
        filtered = filtered[filtered["rarity"] == rarity_filter]
    if signal_filter != "Sve":
        filtered = filtered[filtered["signal"] == signal_filter]

    if filtered.empty:
        st.sidebar.warning("Nema karata za taj upit.")
        filtered = market

    labels = {
        row.id: f"{row.name}  ·  {row.id}  ·  ${row.price:.2f}  ·  {row.signal}"
        for row in filtered.itertuples(index=False)
    }
    selected_id = st.sidebar.selectbox(
        "Odaberi kartu",
        options=list(labels.keys()),
        format_func=lambda card_id: labels[card_id],
    )
    card = market.loc[market["id"] == selected_id].iloc[0]
    series = card_history(history, str(card["id"]))
    if series.empty:
        st.error("Za odabranu kartu nema redaka u price_history.")
        return

    last_price = float(series["price"].iloc[-1])
    previous_price = float(series["price"].iloc[-2]) if len(series) > 1 else last_price
    predicted = float(card["predicted_price"])
    change_pct = (predicted - last_price) / last_price * 100.0
    day_change_pct = (last_price - previous_price) / previous_price * 100.0 if previous_price else 0.0
    period_change_pct = (last_price / float(series["price"].iloc[0]) - 1.0) * 100.0
    signal = trading_signal(last_price, predicted)
    next_day = (pd.Timestamp(series["date"].iloc[-1]) + pd.Timedelta(days=1)).strftime("%d.%m.%Y")

    left, right = st.columns([1.2, 0.8], gap="large")
    with left:
        st.subheader(str(card["name"]))
        chip_row(
            [
                ("Set", str(card["set_name"])),
                ("Rijetkost", str(card["rarity"])),
                ("Zadnje zatvaranje", f"${last_price:.4f}"),
                ("Dnevna promjena", f"{day_change_pct:+.2f}%"),
            ],
            "detail-row",
        )
        chip_row(
            [
                ("60d min", f"${float(series['price'].min()):.4f}"),
                ("60d max", f"${float(series['price'].max()):.4f}"),
                ("Promjena 60d", f"{period_change_pct:+.1f}%"),
            ],
            "stat-row",
        )
        st.plotly_chart(
            price_chart(series, predicted, str(card["name"])),
            width="stretch",
        )

    with right:
        st.subheader("AI predikcija (XGBoost)")
        st.metric(
            f"Cijena {next_day}",
            f"${predicted:.4f}",
            delta=f"{predicted - last_price:+.4f} USD ({change_pct:+.2f}%)",
        )
        st.markdown(
            f'<div class="{SIGNAL_CLASS[signal]}">{signal}</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"Očekivana promjena: **{change_pct:+.2f}%**. "
            f"DRŽI unutar ±{HOLD_BAND * 100:.2f}%, inače KUPI ili PRODAJ."
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "Polje": [
                        "ID",
                        "Supertype",
                        "Točaka u nizu",
                        "Cijena jučer",
                        "7-dnevni prosjek",
                    ],
                    "Vrijednost": [
                        str(card["id"]),
                        str(card["supertype"]),
                        str(len(series)),
                        f"${float(card['price_lag_1']):.4f}",
                        f"${float(card['rolling_mean_7']):.4f}",
                    ],
                }
            ),
            hide_index=True,
            width="stretch",
        )

    st.divider()
    st.subheader("Pregled tržišta")
    overview = market[
        ["id", "name", "set_name", "rarity", "price", "predicted_price", "expected_change_pct", "signal"]
    ].rename(
        columns={
            "id": "ID",
            "name": "Ime",
            "set_name": "Set",
            "rarity": "Rijetkost",
            "price": "Zatvaranje",
            "predicted_price": "AI sljedeći dan",
            "expected_change_pct": "Očekivano %",
            "signal": "Signal",
        }
    )
    st.dataframe(
        overview,
        width="stretch",
        height=360,
        column_config={
            "Zatvaranje": st.column_config.NumberColumn(format="$%.4f"),
            "AI sljedeći dan": st.column_config.NumberColumn(format="$%.4f"),
            "Očekivano %": st.column_config.NumberColumn(format="%+.2f%%"),
        },
    )

    counts = market["signal"].value_counts()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Karata", len(market))
    m2.metric("KUPI", int(counts.get("KUPI", 0)))
    m3.metric("DRŽI", int(counts.get("DRŽI", 0)))
    m4.metric("PRODAJ", int(counts.get("PRODAJ", 0)))


if __name__ == "__main__":
    main()

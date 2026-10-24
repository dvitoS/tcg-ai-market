# pip install streamlit plotly
"""TCG AI Market Dashboard — stvarna povijest cijena i XGBoost."""

from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ai_xgboost import (
    FEATURE_COLUMNS,
    add_time_features,
    card_forecasts,
    drop_incomplete_rows,
    load_history,
    resample_daily_history,
    split_features,
    train_xgboost,
)
from database import add_portfolio_position, engine, init_db

st.set_page_config(
    page_title="TCG AI Market Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Promjena unutar ovog pojasa ostaje DRŽI; izvan njega je KUPI ili PRODAJ.
HOLD_BAND = 0.0035
FORECAST_DAYS = 7
SCANNER_GROWTH_FLOOR = 10.0
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
    .signal-pct {
        margin-top: 6px;
        font-size: 1.05rem;
        letter-spacing: 0.04em;
        font-weight: 650;
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
    .chip-value.pnl-up { color: #4ade80 !important; }
    .chip-value.pnl-down { color: #f87171 !important; }
    .ai-outlook {
        border-radius: 14px;
        padding: 16px 18px;
        margin: 4px 0 16px;
        font-size: 1.05rem;
        font-weight: 650;
        line-height: 1.45;
    }
    .ai-outlook.up { background: #14532d; border: 1px solid #22c55e; }
    .ai-outlook.down { background: #7f1d1d; border: 1px solid #f87171; }
    .ai-outlook.flat { background: #1e293b; border: 1px solid #64748b; }
    .scanner-title {
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        margin: 18px 0 8px;
    }
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
def load_exchange() -> tuple[pd.DataFrame, pd.DataFrame, object]:
    history = load_history()
    featured, _encoders = add_time_features(history)
    trainable = drop_incomplete_rows(featured)
    X_train, _X_test, y_train, _y_test = split_features(trainable)
    model = train_xgboost(X_train, y_train)
    quotes = assign_signals(card_forecasts(model, featured))
    return history, quotes.sort_values("name").reset_index(drop=True), model


def card_history(history: pd.DataFrame, card_id: str) -> pd.DataFrame:
    """Isti dnevni resampling kao u treningu: mean po danu, zatim ffill."""
    raw = history.loc[history["card_id"] == card_id].sort_values("date")
    if raw.empty:
        return raw.reset_index(drop=True)
    return resample_daily_history(raw.copy()).reset_index(drop=True)


def lag_features_for_last_day(series: pd.DataFrame) -> dict[str, float] | None:
    """Lag 1/3/7 i 7-dnevni prosjek na zadnjem danu očišćenog niza."""
    prices = series.sort_values("date")["price"].astype(float).reset_index(drop=True)
    if len(prices) < 8:
        return None
    return {
        "price_lag_1": float(prices.iloc[-2]),
        "price_lag_3": float(prices.iloc[-4]),
        "price_lag_7": float(prices.iloc[-8]),
        "rolling_mean_7": float(prices.iloc[-7:].mean()),
    }


def predict_from_prices(model, prices, rarity_encoded: float, supertype_encoded: float) -> float | None:
    """Jedan korak unaprijed iz zadnjih cijena. Lagovi su isti kao u treningu."""
    values = pd.Series(prices, dtype=float).reset_index(drop=True)
    if len(values) < 8:
        return None
    row = {
        "price_lag_1": float(values.iloc[-2]),
        "price_lag_3": float(values.iloc[-4]),
        "price_lag_7": float(values.iloc[-8]),
        "rolling_mean_7": float(values.iloc[-7:].mean()),
        "rarity_encoded": float(rarity_encoded),
        "supertype_encoded": float(supertype_encoded),
    }
    features = pd.DataFrame([row])[FEATURE_COLUMNS]
    return float(model.predict(features)[0])


def predict_next_close(model, series: pd.DataFrame, rarity_encoded: float, supertype_encoded: float) -> float | None:
    prices = series.sort_values("date")["price"]
    return predict_from_prices(model, prices, rarity_encoded, supertype_encoded)


def forecast_price_in_days(
    model,
    series: pd.DataFrame,
    rarity_encoded: float,
    supertype_encoded: float,
    days: int = FORECAST_DAYS,
) -> float | None:
    """Sedam uzastopnih dnevnih prognoza: svaki korak ulazi u lagove sljedećeg."""
    prices = series.sort_values("date")["price"].astype(float).tolist()
    for _ in range(days):
        nxt = predict_from_prices(model, prices, rarity_encoded, supertype_encoded)
        if nxt is None:
            return None
        prices.append(max(nxt, 0.0))
    return prices[-1]


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


def signed_dollars(amount: float) -> str:
    sign = "+" if amount > 0 else "-" if amount < 0 else ""
    return f"{sign}${abs(amount):.2f}"


def load_portfolio_lots() -> pd.DataFrame:
    return pd.read_sql(
        """
        SELECT
            p.id,
            p.card_id,
            p.quantity,
            p.purchase_price,
            p.purchase_date,
            c.name,
            c.market_price
        FROM portfolio AS p
        INNER JOIN cards AS c ON c.id = p.card_id
        ORDER BY p.id
        """,
        engine,
    )


def portfolio_view(lots: pd.DataFrame, market: pd.DataFrame, history: pd.DataFrame, model) -> pd.DataFrame:
    """Spaja nabave sa zadnjim zatvaranjem i 7-dnevnom prognozom."""
    quotes = market[["id", "price", "rarity_encoded", "supertype_encoded"]].rename(columns={"id": "card_id"})
    view = lots.merge(quotes, on="card_id", how="left")
    view["current_price"] = view["price"].fillna(view["market_price"]).astype(float)
    view["invested"] = view["quantity"] * view["purchase_price"]
    view["market_value"] = view["quantity"] * view["current_price"]
    view["pnl"] = view["market_value"] - view["invested"]
    view["pnl_pct"] = np.where(view["invested"] > 0, view["pnl"] / view["invested"] * 100.0, 0.0)

    week_prices: list[float] = []
    for lot in view.itertuples(index=False):
        series = card_history(history, str(lot.card_id))
        if series.empty or pd.isna(lot.rarity_encoded):
            week_prices.append(float(lot.current_price))
            continue
        forecast = forecast_price_in_days(
            model,
            series,
            float(lot.rarity_encoded),
            float(lot.supertype_encoded),
        )
        week_prices.append(float(forecast) if forecast is not None else float(lot.current_price))
    view["week_price"] = week_prices
    view["week_value"] = view["quantity"] * view["week_price"]
    return view


def render_portfolio_kpis(value: float, invested: float, pnl: float, pnl_pct: float) -> None:
    tone = "pnl-up" if pnl > 0 else "pnl-down" if pnl < 0 else ""
    pnl_text = f"{signed_dollars(pnl)} / {pnl_pct:+.1f}%"
    cells = [
        ("Ukupna vrijednost kolekcije", f"${value:.2f}", ""),
        ("Ukupno uloženo", f"${invested:.2f}", ""),
        ("Ukupni P&L", pnl_text, tone),
    ]
    html = "".join(
        f'<div class="chip"><div class="chip-label">{escape(label)}</div>'
        f'<div class="chip-value {css}">{escape(text)}</div></div>'
        for label, text, css in cells
    )
    st.markdown(f'<div class="stat-row">{html}</div>', unsafe_allow_html=True)


def render_week_outlook(current_value: float, week_value: float) -> None:
    if current_value <= 0:
        return
    change_pct = (week_value - current_value) / current_value * 100.0
    if change_pct > 0.05:
        tone = "up"
        sentence = (
            f"AI predviđa da će vrijednost vašeg portfelja idući tjedan porasti za {change_pct:.1f}%."
        )
    elif change_pct < -0.05:
        tone = "down"
        sentence = (
            f"AI predviđa da će vrijednost vašeg portfelja idući tjedan pasti za {abs(change_pct):.1f}%."
        )
    else:
        tone = "flat"
        sentence = "AI predviđa da će vrijednost vašeg portfelja idući tjedan ostati približno ista."
    st.markdown(f'<div class="ai-outlook {tone}">{escape(sentence)}</div>', unsafe_allow_html=True)
    st.caption(
        f"Sada \\${current_value:.2f} → \\${week_value:.2f} za {FORECAST_DAYS} dana. "
        "Tjedan je sedam uzastopnih prognoza sljedećeg dana istim XGBoost modelom."
    )


def render_market(history: pd.DataFrame, market: pd.DataFrame, model) -> None:
    st.subheader("Tražilica karata")
    filters = st.columns([1.4, 1, 1])
    query = filters[0].text_input("Pretraži po imenu", placeholder="npr. Pikachu, Charizard...")
    rarities = ["Sve"] + sorted(market["rarity"].dropna().unique().tolist())
    rarity_filter = filters[1].selectbox("Rijetkost", rarities)
    signal_filter = filters[2].selectbox("Signal", ["Sve", "KUPI", "PRODAJ", "DRŽI"])

    filtered = market
    if query.strip():
        filtered = filtered[filtered["name"].str.contains(query.strip(), case=False, na=False)]
    if rarity_filter != "Sve":
        filtered = filtered[filtered["rarity"] == rarity_filter]
    if signal_filter != "Sve":
        filtered = filtered[filtered["signal"] == signal_filter]

    if filtered.empty:
        st.warning("Nema karata za taj upit.")
        filtered = market

    labels = {
        row.id: f"{row.name}  ·  {row.id}  ·  ${row.price:.2f}  ·  {row.signal}"
        for row in filtered.itertuples(index=False)
    }
    selected_id = st.selectbox(
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
    predicted = predict_next_close(
        model,
        series,
        float(card["rarity_encoded"]),
        float(card["supertype_encoded"]),
    )
    if predicted is None:
        st.warning("Niz je kraći od 8 dana, pa lagovi za sutrašnju prognozu još nisu dostupni.")
        predicted = float(card["predicted_price"])
    change_pct = (predicted - last_price) / last_price * 100.0
    lags = lag_features_for_last_day(series) or {
        "price_lag_1": float(card["price_lag_1"]),
        "rolling_mean_7": float(card["rolling_mean_7"]),
    }
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
            f'<div class="{SIGNAL_CLASS[signal]}">{signal}'
            f'<div class="signal-pct">{change_pct:+.2f}%</div></div>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"Postotak je očekivana promjena cijene sutra. "
            f"DRŽI unutar ±{HOLD_BAND * 100:.2f}%, inače KUPI ili PRODAJ. "
            "Značajke: cijena od jučer, prije 3 i 7 dana te 7-dnevni prosjek."
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
                        f"${float(lags['price_lag_1']):.4f}",
                        f"${float(lags['rolling_mean_7']):.4f}",
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


@st.cache_data(show_spinner=False)
def build_ai_scan(history: pd.DataFrame, market: pd.DataFrame, _model) -> pd.DataFrame:
    """Za svaku kartu: lagovi → XGBoost → cijena za 7 dana i ROI.

    history iz load_exchange već je dnevno resamplean, pa ovdje samo filtriramo.
    """
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
                "Naziv": str(card.name),
                "Set": str(card.set_name),
                "Trenutna cijena": current,
                "AI Ciljna cijena": target,
                "Očekivani ROI (%)": (target - current) / current * 100.0,
                "id": str(card.id),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=["Naziv", "Set", "Trenutna cijena", "AI Ciljna cijena", "Očekivani ROI (%)", "id"]
        )
    return pd.DataFrame(rows).sort_values("Očekivani ROI (%)", ascending=False).reset_index(drop=True)


def scanner_table(frame: pd.DataFrame, height: int = 320) -> None:
    display = frame[["Naziv", "Set", "Trenutna cijena", "AI Ciljna cijena", "Očekivani ROI (%)"]]
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        height=height,
        column_config={
            "Naziv": st.column_config.TextColumn("Naziv", width="medium"),
            "Set": st.column_config.TextColumn("Set", width="medium"),
            "Trenutna cijena": st.column_config.NumberColumn(format="$%.4f"),
            "AI Ciljna cijena": st.column_config.NumberColumn(format="$%.4f"),
            "Očekivani ROI (%)": st.column_config.NumberColumn(format="%+.2f%%"),
        },
    )


def render_scanner(history: pd.DataFrame, market: pd.DataFrame, model) -> None:
    st.subheader("🤖 AI Scanner")
    st.caption(
        f"XGBoost pregled svih karata · cilj za {FORECAST_DAYS} dana iz lagova "
        "(jučer, −3d, −7d, 7-dnevni prosjek)."
    )

    sets = ["Svi setovi"] + sorted(market["set_name"].dropna().unique().tolist())
    filters = st.columns([1.4, 1, 1])
    set_filter = filters[0].selectbox("Set", sets, key="scanner_set")
    min_growth = filters[1].number_input(
        "Min. rast za TOP prilike (%)",
        min_value=0.0,
        max_value=100.0,
        value=float(SCANNER_GROWTH_FLOOR),
        step=1.0,
        key="scanner_min_growth",
    )
    max_rows = filters[2].number_input(
        "Max. redova po sekciji",
        min_value=5,
        max_value=100,
        value=25,
        step=5,
        key="scanner_max_rows",
    )

    with st.spinner("Skeniram sve karte XGBoost modelom..."):
        scan = build_ai_scan(history, market, model)

    if scan.empty:
        st.warning("Nema dovoljno povijesti za AI sken. Provjeri price_history.")
        return

    scoped = scan if set_filter == "Svi setovi" else scan.loc[scan["Set"] == set_filter]
    if scoped.empty:
        st.warning(f"Nema karata za set {set_filter}.")
        return

    opportunities = (
        scoped.loc[scoped["Očekivani ROI (%)"] >= float(min_growth)]
        .sort_values("Očekivani ROI (%)", ascending=False)
        .head(int(max_rows))
        .reset_index(drop=True)
    )
    warnings = (
        scoped.loc[scoped["Očekivani ROI (%)"] < 0]
        .sort_values("Očekivani ROI (%)", ascending=True)
        .head(int(max_rows))
        .reset_index(drop=True)
    )

    k1, k2, k3 = st.columns(3)
    k1.metric("Skenirano karata", len(scoped))
    k2.metric("TOP prilike", len(opportunities), delta=f"≥ {min_growth:.0f}%")
    k3.metric("Upozorenja za pad", len(warnings))

    st.markdown(
        f'<div class="scanner-title">🔥 TOP AI PRILIKE '
        f'(rast ≥ {min_growth:.0f}%)</div>',
        unsafe_allow_html=True,
    )
    if opportunities.empty:
        st.info(
            f"Nema karata s očekivanim rastom iznad {min_growth:.0f}% "
            "za odabrani set. Spusti prag filtera."
        )
    else:
        scanner_table(opportunities)

    st.markdown(
        '<div class="scanner-title">⚠️ AI UPOZORENJA ZA PAD</div>',
        unsafe_allow_html=True,
    )
    if warnings.empty:
        st.success("Nema karata s predviđenim padom za odabrani filter.")
    else:
        scanner_table(warnings)


def render_portfolio(history: pd.DataFrame, market: pd.DataFrame, model) -> None:
    st.subheader("Dodaj kartu")
    labels = {
        row.id: f"{row.name}  ·  {row.id}  ·  ${row.price:.2f}"
        for row in market.sort_values("name").itertuples(index=False)
    }
    with st.form("add_portfolio", clear_on_submit=True):
        picked, quantity, purchase_price = st.columns([2, 1, 1])
        card_id = picked.selectbox(
            "Karta",
            options=list(labels.keys()),
            format_func=lambda item: labels[item],
        )
        qty = quantity.number_input("Količina", min_value=1, step=1, value=1)
        cost = purchase_price.number_input(
            "Nabavna cijena (USD)",
            min_value=0.0001,
            step=0.01,
            value=0.10,
            format="%.4f",
        )
        submitted = st.form_submit_button("Dodaj u portfelj", type="primary")

    if submitted:
        try:
            add_portfolio_position(str(card_id), int(qty), float(cost))
        except ValueError as exc:
            st.error(str(exc))
        else:
            name = str(market.loc[market["id"] == card_id, "name"].iloc[0])
            st.session_state["portfolio_notice"] = f"{name} je dodan u portfelj."
            st.rerun()

    notice = st.session_state.pop("portfolio_notice", None)
    if notice:
        st.success(notice)

    lots = load_portfolio_lots()
    if lots.empty:
        render_portfolio_kpis(0.0, 0.0, 0.0, 0.0)
        st.info("Portfelj je prazan. Odaberi kartu, količinu i nabavnu cijenu.")
        return

    view = portfolio_view(lots, market, history, model)
    value = float(view["market_value"].sum())
    invested = float(view["invested"].sum())
    pnl = float(view["pnl"].sum())
    pnl_pct = pnl / invested * 100.0 if invested else 0.0
    render_portfolio_kpis(value, invested, pnl, pnl_pct)
    render_week_outlook(value, float(view["week_value"].sum()))

    table = pd.DataFrame(
        {
            "Naziv karte": view["name"],
            "Količina": view["quantity"].astype(int),
            "Nabavna cijena": view["purchase_price"],
            "Trenutna tržišna cijena": view["current_price"],
            "Trenutna ukupna vrijednost": view["market_value"],
            "P&L": [
                f"{signed_dollars(amount)} / {pct:+.1f}%"
                for amount, pct in zip(view["pnl"], view["pnl_pct"], strict=True)
            ],
        }
    )
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "Količina": st.column_config.NumberColumn(format="%d"),
            "Nabavna cijena": st.column_config.NumberColumn(format="$%.4f"),
            "Trenutna tržišna cijena": st.column_config.NumberColumn(format="$%.4f"),
            "Trenutna ukupna vrijednost": st.column_config.NumberColumn(format="$%.2f"),
        },
    )


def main() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.title("📈 TCG AI Market Dashboard")
    st.caption("Pokémon TCG burza · portfelj · XGBoost predikcija")

    init_db()
    history, market, model = load_exchange()
    if market.empty or history.empty:
        st.error("Nema povijesti cijena. Pokreni `python generate_history.py`.")
        return

    tab1, tab2, tab3 = st.tabs(["Tržište & AI", "Moj Portfelj", "🤖 AI Scanner"])
    with tab1:
        render_market(history, market, model)
    with tab2:
        render_portfolio(history, market, model)
    with tab3:
        render_scanner(history, market, model)


if __name__ == "__main__":
    main()

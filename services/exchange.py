"""Cached market history + XGBoost model pipeline."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ai_insights import confidence_by_card
from ai_xgboost import (
    add_time_features,
    card_forecasts,
    drop_incomplete_rows,
    load_history,
    split_features,
    train_xgboost,
)
from database import ensure_seed_database, init_db
from generate_history import ensure_price_history
from trading_signals import SIGNAL_HOLD, assign_signals


@st.cache_resource(show_spinner=False)
def load_exchange() -> tuple[pd.DataFrame, pd.DataFrame, object]:
    """Load history, train model, assign signals.

    Cached as a resource so Streamlit reruns do not retrain XGBoost every click.
    Clear via clear_exchange_cache() after catalog sync / nightly.
    """
    from config import CATALOG_MIN_PRICE

    init_db()
    if ensure_seed_database():
        pass
    else:
        ensure_price_history()
    history = load_history()
    featured, _encoders = add_time_features(history)
    trainable = drop_incomplete_rows(featured)
    X_train, _X_test, y_train, _y_test = split_features(trainable)
    model = train_xgboost(X_train, y_train)
    quotes = assign_signals(card_forecasts(model, featured))
    conf = confidence_by_card(history)
    if not conf.empty:
        quotes = quotes.merge(conf, on="id", how="left")
        quotes["confidence_ok"] = quotes["confidence_ok"].fillna(False).astype(bool)
        quotes["confidence_level"] = quotes["confidence_level"].fillna("low")
        # Soft-gate: low-data cards stay visible but signal becomes HOLD.
        low = ~quotes["confidence_ok"]
        if low.any():
            quotes.loc[low, "signal"] = SIGNAL_HOLD
    else:
        quotes["confidence_ok"] = True
        quotes["confidence_level"] = "medium"
        quotes["history_points"] = 0
    spot = pd.to_numeric(quotes.get("price"), errors="coerce")
    if "market_price" in quotes.columns:
        spot = spot.fillna(pd.to_numeric(quotes["market_price"], errors="coerce"))
    quotes = quotes.loc[spot >= float(CATALOG_MIN_PRICE)].copy()
    keep_ids = set(quotes["id"].astype(str)) if "id" in quotes.columns else set()
    if keep_ids and "card_id" in history.columns:
        history = history.loc[history["card_id"].astype(str).isin(keep_ids)].copy()
    return history, quotes.sort_values("name").reset_index(drop=True), model


def clear_exchange_cache() -> None:
    load_exchange.clear()

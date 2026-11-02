"""Cached market history + XGBoost model pipeline."""

from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from ai_insights import confidence_by_card
from ai_xgboost import (
    FEATURE_COLUMNS,
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

LOG = logging.getLogger("tcg.exchange")


def _resolve_model(featured: pd.DataFrame):
    """Load persisted model when possible; otherwise train and save."""
    from services.model_store import load_model_artifact, save_model_artifact

    loaded = load_model_artifact()
    if loaded is not None:
        model, meta = loaded
        cols = list(meta.get("feature_columns") or [])
        if not cols or cols == list(FEATURE_COLUMNS):
            LOG.info(
                "Using persisted XGBoost model (trained_at=%s)",
                meta.get("trained_at"),
            )
            return model, False
        LOG.warning("Persisted model feature mismatch — retraining.")

    trainable = drop_incomplete_rows(featured)
    X_train, _X_test, y_train, _y_test = split_features(trainable)
    model = train_xgboost(X_train, y_train)
    try:
        save_model_artifact(
            model,
            metrics={"rows": int(len(trainable)), "source": "load_exchange"},
            feature_columns=list(FEATURE_COLUMNS),
        )
    except Exception as exc:
        LOG.warning("Could not persist freshly trained model: %s", exc)
    return model, True


@st.cache_resource(show_spinner=False)
def load_exchange() -> tuple[pd.DataFrame, pd.DataFrame, object]:
    """Load history, resolve model (persisted or train), assign signals.

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
    model, _trained_now = _resolve_model(featured)
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

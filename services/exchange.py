"""Cached market history + XGBoost model pipeline."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from ai_insights import confidence_by_card
from ai_xgboost import (
    FEATURE_COLUMNS,
    add_time_features,
    apply_label_maps,
    card_forecasts,
    drop_incomplete_rows,
    label_maps_from_encoders,
    load_history,
    split_features,
    train_xgboost,
)
from database import ensure_seed_database, init_db
from generate_history import ensure_price_history
from trading_signals import SIGNAL_HOLD, assign_signals

LOG = logging.getLogger("tcg.exchange")


def _label_maps_from_meta(meta: dict | None) -> dict[str, dict[str, int]] | None:
    metrics = (meta or {}).get("metrics") or {}
    maps = metrics.get("label_maps")
    if not isinstance(maps, dict):
        return None
    rarity = maps.get("rarity")
    supertype = maps.get("supertype")
    if isinstance(rarity, dict) and isinstance(supertype, dict) and rarity and supertype:
        return {
            "rarity": {str(k): int(v) for k, v in rarity.items()},
            "supertype": {str(k): int(v) for k, v in supertype.items()},
        }
    return None


def _quotes_have_encodings(quotes: pd.DataFrame) -> bool:
    if "rarity_encoded" not in quotes.columns or "supertype_encoded" not in quotes.columns:
        return False
    return bool(quotes["rarity_encoded"].notna().any() and quotes["supertype_encoded"].notna().any())


def ensure_quote_encodings(
    quotes: pd.DataFrame,
    history: pd.DataFrame | None = None,
    *,
    meta: dict | None = None,
) -> pd.DataFrame:
    """Guarantee rarity_encoded / supertype_encoded on the market board."""
    if quotes is None or quotes.empty:
        return quotes
    if _quotes_have_encodings(quotes):
        return quotes

    maps = _label_maps_from_meta(meta)
    if maps is not None:
        LOG.info("Applying persisted label_maps to market quotes.")
        return apply_label_maps(quotes, maps)

    if history is not None and not history.empty:
        featured, encoders = add_time_features(history)
        latest = (
            featured.sort_values(["card_id", "date"])
            .groupby("card_id", as_index=False)
            .tail(1)[["card_id", "rarity_encoded", "supertype_encoded"]]
            .rename(columns={"card_id": "id"})
        )
        out = quotes.drop(
            columns=[c for c in ("rarity_encoded", "supertype_encoded") if c in quotes.columns],
            errors="ignore",
        ).merge(latest, on="id", how="left")
        derived = label_maps_from_encoders(encoders)
        missing = out["rarity_encoded"].isna() | out["supertype_encoded"].isna()
        if missing.any():
            filled = apply_label_maps(out.loc[missing], derived)
            out.loc[missing, "rarity_encoded"] = filled["rarity_encoded"].to_numpy()
            out.loc[missing, "supertype_encoded"] = filled["supertype_encoded"].to_numpy()
        LOG.info("Derived quote encodings from history features.")
        return out

    if "rarity" in quotes.columns and "supertype" in quotes.columns:
        from sklearn.preprocessing import LabelEncoder

        out = quotes.copy()
        for column, encoded_name in (
            ("rarity", "rarity_encoded"),
            ("supertype", "supertype_encoded"),
        ):
            encoder = LabelEncoder()
            values = out[column].fillna("Unknown").astype(str)
            out[encoded_name] = encoder.fit_transform(values).astype("float64")
        LOG.warning("Encoded quotes from text columns only (no history/maps).")
        return out

    return quotes


def _resolve_model(featured: pd.DataFrame, *, encoders: dict | None = None):
    """Load persisted model when possible; otherwise train and save."""
    from services.model_store import load_model_artifact, save_model_artifact

    label_maps = label_maps_from_encoders(encoders) if encoders else None

    loaded = load_model_artifact()
    if loaded is not None:
        model, meta = loaded
        cols = list(meta.get("feature_columns") or [])
        if not cols or cols == list(FEATURE_COLUMNS):
            LOG.info(
                "Using persisted XGBoost model (trained_at=%s)",
                meta.get("trained_at"),
            )
            if label_maps and _label_maps_from_meta(meta) is None:
                try:
                    metrics = dict(meta.get("metrics") or {})
                    metrics["label_maps"] = label_maps
                    save_model_artifact(
                        model,
                        metrics=metrics,
                        feature_columns=list(FEATURE_COLUMNS),
                    )
                except Exception as exc:
                    LOG.warning("Could not persist label_maps on existing model: %s", exc)
            return model, False
        LOG.warning("Persisted model feature mismatch — retraining.")

    trainable = drop_incomplete_rows(featured)
    X_train, _X_test, y_train, _y_test = split_features(trainable)
    model = train_xgboost(X_train, y_train)
    try:
        metrics: dict = {"rows": int(len(trainable)), "source": "load_exchange"}
        if label_maps:
            metrics["label_maps"] = label_maps
        save_model_artifact(
            model,
            metrics=metrics,
            feature_columns=list(FEATURE_COLUMNS),
        )
    except Exception as exc:
        LOG.warning("Could not persist freshly trained model: %s", exc)
    return model, True


def _apply_confidence(quotes: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    conf = confidence_by_card(history)
    if not conf.empty:
        out = quotes.merge(conf, on="id", how="left")
        out["confidence_ok"] = out["confidence_ok"].fillna(False).astype(bool)
        out["confidence_level"] = out["confidence_level"].fillna("low")
        low = ~out["confidence_ok"]
        if low.any():
            out.loc[low, "signal"] = SIGNAL_HOLD
        return out
    out = quotes.copy()
    out["confidence_ok"] = True
    out["confidence_level"] = "medium"
    out["history_points"] = 0
    return out


def _filter_catalog_floor(quotes: pd.DataFrame) -> pd.DataFrame:
    from config import CATALOG_MIN_PRICE

    spot = pd.to_numeric(quotes.get("price"), errors="coerce")
    if "market_price" in quotes.columns:
        spot = spot.fillna(pd.to_numeric(quotes["market_price"], errors="coerce"))
    return quotes.loc[spot >= float(CATALOG_MIN_PRICE)].copy()


def build_market_board(
    *,
    persist: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, object]:
    """Full rebuild: history → model → quotes. Used by nightly and slow-path boot."""
    from services.quotes_store import save_market_quotes

    history = load_history()
    featured, encoders = add_time_features(history)
    model, _trained_now = _resolve_model(featured, encoders=encoders)
    quotes = assign_signals(card_forecasts(model, featured))
    quotes = _apply_confidence(quotes, history)
    quotes = _filter_catalog_floor(quotes)
    quotes = quotes.sort_values("name").reset_index(drop=True)
    keep_ids = set(quotes["id"].astype(str)) if "id" in quotes.columns else set()
    if keep_ids and "card_id" in history.columns:
        history = history.loc[history["card_id"].astype(str).isin(keep_ids)].copy()
    if persist:
        try:
            saved = save_market_quotes(quotes)
            LOG.info("Persisted market_quotes rows=%s", saved)
        except Exception as exc:
            LOG.warning("market_quotes persist failed: %s", exc)
    return history, quotes, model


def _try_fast_boot() -> tuple[pd.DataFrame, pd.DataFrame, object] | None:
    """Load precomputed quotes + model + scoped history when available."""
    from config import PRICE_HISTORY_DAYS
    from services.model_store import load_model_artifact
    from services.quotes_store import load_market_quotes

    quotes = load_market_quotes()
    if quotes is None or quotes.empty:
        return None
    loaded = load_model_artifact()
    if loaded is None:
        return None
    model, meta = loaded
    cols = list(meta.get("feature_columns") or [])
    if cols and cols != list(FEATURE_COLUMNS):
        LOG.warning("Skipping fast boot — feature mismatch on persisted model.")
        return None

    quotes = _filter_catalog_floor(quotes)
    if quotes.empty:
        return None
    card_ids = quotes["id"].astype(str).tolist()
    since = (date.today() - timedelta(days=int(PRICE_HISTORY_DAYS) + 14)).isoformat()
    try:
        history = load_history(card_ids=card_ids, since_date=since)
    except Exception as exc:
        LOG.warning("Fast boot history load failed: %s", exc)
        return None
    quotes = ensure_quote_encodings(quotes, history, meta=meta)
    if not _quotes_have_encodings(quotes):
        LOG.warning("Fast boot skipped — could not attach rarity/supertype encodings.")
        return None
    LOG.info(
        "Fast boot: quotes=%s history_rows=%s model_trained_at=%s",
        len(quotes),
        len(history),
        meta.get("trained_at"),
    )
    return history, quotes.sort_values("name").reset_index(drop=True), model


@st.cache_resource(show_spinner=False)
def load_exchange() -> tuple[pd.DataFrame, pd.DataFrame, object]:
    """Load history + model + signals.

    Prefers nightly `market_quotes` + persisted model (fast). Falls back to a full
    rebuild and persists quotes for the next boot.
    """
    init_db()
    if ensure_seed_database():
        pass
    else:
        ensure_price_history()

    fast = _try_fast_boot()
    if fast is not None:
        return fast
    return build_market_board(persist=True)


def clear_exchange_cache() -> None:
    load_exchange.clear()

# pip install xgboost scikit-learn
# pip install matplotlib   # opcionalno, za graf feature importance
"""XGBoost: 7-day forward return prediction (not absolute next-day price)."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from database import load_history_frame
from trading_signals import (
    FORECAST_DAYS,
    FORECAST_SIGNAL_BAND,
    PORTFOLIO_CONFORMAL_WIDTH_CAP,
    PORTFOLIO_HORIZON_DAYS,
    PORTFOLIO_SIGNAL_BAND,
)

RANDOM_SEED = 42
TEST_SIZE = 0.2
# Default board/scanner horizon (7d). Portfolio uses PORTFOLIO_HORIZON_DAYS via retrain.
HORIZON_DAYS = int(FORECAST_DAYS)
# Days with |7d return| below this count as flat for direction scoring.
RETURN_HOLD_BAND = float(FORECAST_SIGNAL_BAND)
# Split conformal: 80% prediction intervals on holdout absolute residuals.
CONFORMAL_ALPHA = 0.20
# Gate BUY/SELL when interval width (return units) exceeds this.
CONFORMAL_WIDTH_CAP = 0.25
ARTIFACT_ID_7D = "latest"
ARTIFACT_ID_30D = "latest_30d"

# Flat day = |1d return| below this (ffill-aware stale-quote proxy).
FLAT_RET_EPS = 1e-4

RETURN_FEATURES = [
    "ret_1",
    "ret_3",
    "ret_7",
    "vol_7",
    "dist_ma_7",
    "dist_ma_30",
    "log_price",
    "set_ret_7",
    "rel_ret_7",
    # Liquidity proxies from price path (no eBay/volume API required).
    "mean_abs_ret_7",
    "flat_share_14",
    "hl_range_14",
    # eBay Browse depth (from ebay_liquidity_snapshots; 0 until harvested).
    "ebay_active_n_log",
    "ebay_ask_premium",
    "ebay_has_obs",
]
FEATURE_COLUMNS = RETURN_FEATURES + ["rarity_encoded", "supertype_encoded"]
FEATURE_LABELS = {
    "ret_1": "1d return",
    "ret_3": "3d return",
    "ret_7": "7d return",
    "vol_7": "7d volatility",
    "dist_ma_7": "vs 7d MA",
    "dist_ma_30": "vs 30d MA",
    "log_price": "log price",
    "set_ret_7": "set median 7d return",
    "rel_ret_7": "card vs set 7d",
    "mean_abs_ret_7": "7d mean |return| (activity)",
    "flat_share_14": "14d flat-day share (illiquidity)",
    "hl_range_14": "14d high-low range",
    "ebay_active_n_log": "eBay active depth (log)",
    "ebay_ask_premium": "eBay ask vs spot",
    "ebay_has_obs": "eBay snapshot present",
    "rarity_encoded": "rarity",
    "supertype_encoded": "supertype",
}
# Back-compat alias (old lag names no longer used as model inputs).
LAG_FEATURES = RETURN_FEATURES


def load_history(
    *,
    card_ids: list[str] | set[str] | None = None,
    since_date: str | None = None,
) -> pd.DataFrame:
    print("Učitavam price_history spojenu s cards (Supabase)...")
    df = load_history_frame(card_ids=card_ids, since_date=since_date)
    if df.empty:
        raise RuntimeError("price_history je prazna. Pokreni generate_history.py ili seed import.")
    df["date"] = pd.to_datetime(df["date"])
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["market_price"] = pd.to_numeric(df["market_price"], errors="coerce")
    df["name"] = df["name"].fillna("").astype(str)
    df["rarity"] = df["rarity"].fillna("Unknown").astype(str)
    df["supertype"] = df["supertype"].fillna("Unknown").astype(str)
    df["set_name"] = df["set_name"].fillna("Unknown").astype(str)
    df = df.dropna(subset=["price", "card_id", "date"])
    df = df.sort_values(["card_id", "date"]).reset_index(drop=True)
    print(f"Učitano {len(df)} snimki za {df['card_id'].nunique()} karata.")
    return resample_daily_history(df)


def resample_daily_history(df: pd.DataFrame) -> pd.DataFrame:
    """Nepravilne PokéWallet snimke pretvara u dnevni niz: mean po danu, zatim ffill."""
    print("Resampling po card_id: .resample('D').mean() + .ffill()...")
    if df.empty:
        return df

    meta_columns = ["name", "supertype", "rarity", "set_name", "market_price"]
    frames: list[pd.DataFrame] = []
    for card_id, group in df.groupby("card_id", sort=False):
        indexed = group.sort_values("date").set_index("date")
        daily_price = indexed["price"].resample("D").mean().ffill().dropna()
        if daily_price.empty:
            continue
        daily = daily_price.rename("price").reset_index()
        daily["card_id"] = card_id
        for column in meta_columns:
            daily[column] = indexed[column].iloc[0]
        frames.append(daily)

    if not frames:
        print("Nakon resamplinga nema dnevnih cijena.")
        return df.iloc[0:0].copy()

    resampled = pd.concat(frames, ignore_index=True)
    resampled = resampled.sort_values(["card_id", "date"]).reset_index(drop=True)
    print(
        f"Nakon resamplinga: {len(resampled)} dnevnih cijena "
        f"za {resampled['card_id'].nunique()} karata."
    )
    return resampled


def add_time_features(
    df: pd.DataFrame,
    *,
    horizon_days: int | None = None,
) -> tuple[pd.DataFrame, dict[str, LabelEncoder]]:
    """Return / volatility features + forward return target per card."""
    horizon = int(horizon_days if horizon_days is not None else HORIZON_DAYS)
    print(
        f"Feature engineering: returns/vol/MA + {horizon}d forward return "
        "(LabelEncoder rarity, supertype)..."
    )
    featured = df.sort_values(["card_id", "date"]).reset_index(drop=True)
    price = featured.groupby("card_id", sort=False)["price"]
    featured["ret_1"] = price.pct_change(1)
    featured["ret_3"] = price.pct_change(3)
    featured["ret_7"] = price.pct_change(7)
    daily_ret = price.pct_change(1)
    featured["vol_7"] = daily_ret.groupby(featured["card_id"], sort=False).transform(
        lambda s: s.rolling(7, min_periods=7).std()
    )
    featured["ma_7"] = price.transform(lambda s: s.rolling(7, min_periods=7).mean())
    featured["ma_30"] = price.transform(lambda s: s.rolling(30, min_periods=14).mean())
    featured["dist_ma_7"] = featured["price"] / featured["ma_7"] - 1.0
    featured["dist_ma_30"] = featured["price"] / featured["ma_30"] - 1.0
    featured["log_price"] = np.log(featured["price"].clip(lower=1e-6))
    # Set context: median peer 7d return that day ("laggard in a hot set").
    featured["set_ret_7"] = featured.groupby(["set_name", "date"], sort=False)["ret_7"].transform(
        "median"
    )
    featured["rel_ret_7"] = featured["ret_7"] - featured["set_ret_7"]
    # Liquidity proxies: activity, stale/ffill share, high-low dispersion.
    abs_ret = daily_ret.abs()
    featured["mean_abs_ret_7"] = abs_ret.groupby(featured["card_id"], sort=False).transform(
        lambda s: s.rolling(7, min_periods=7).mean()
    )
    flat = (abs_ret < FLAT_RET_EPS).astype(float)
    featured["flat_share_14"] = flat.groupby(featured["card_id"], sort=False).transform(
        lambda s: s.rolling(14, min_periods=14).mean()
    )
    roll_max = price.transform(lambda s: s.rolling(14, min_periods=14).max())
    roll_min = price.transform(lambda s: s.rolling(14, min_periods=14).min())
    roll_mean = price.transform(lambda s: s.rolling(14, min_periods=14).mean())
    featured["hl_range_14"] = (roll_max - roll_min) / roll_mean.clip(lower=1e-6)
    future = price.shift(-horizon)
    featured["target_price"] = future
    featured["target_return"] = future / featured["price"] - 1.0
    featured["horizon_days"] = horizon

    try:
        from services.ebay_liquidity import attach_ebay_features

        featured = attach_ebay_features(featured)
    except Exception as exc:
        print(f"eBay liquidity features skipped: {exc}")
        featured["ebay_active_n_log"] = 0.0
        featured["ebay_ask_premium"] = 0.0
        featured["ebay_has_obs"] = 0.0

    encoders: dict[str, LabelEncoder] = {}
    for column, encoded_name in (
        ("rarity", "rarity_encoded"),
        ("supertype", "supertype_encoded"),
    ):
        encoder = LabelEncoder()
        featured[encoded_name] = encoder.fit_transform(featured[column])
        encoders[column] = encoder
        mapping = {
            str(label): int(code)
            for label, code in zip(encoder.classes_, encoder.transform(encoder.classes_))
        }
        print(f"  {column}: {mapping}")
    return featured, encoders


def label_maps_from_encoders(encoders: dict[str, LabelEncoder]) -> dict[str, dict[str, int]]:
    """Serialize LabelEncoder vocabularies for fast-boot quote encoding."""
    maps: dict[str, dict[str, int]] = {}
    for column, encoder in encoders.items():
        maps[column] = {
            str(label): int(code)
            for label, code in zip(encoder.classes_, encoder.transform(encoder.classes_))
        }
    return maps


def apply_label_maps(frame: pd.DataFrame, label_maps: dict[str, dict[str, int]]) -> pd.DataFrame:
    """Attach rarity_encoded / supertype_encoded from persisted string→code maps."""
    out = frame.copy()
    for column, encoded_name in (
        ("rarity", "rarity_encoded"),
        ("supertype", "supertype_encoded"),
    ):
        mapping = label_maps.get(column) or {}
        if not mapping:
            continue
        series = out[column] if column in out.columns else pd.Series("Unknown", index=out.index)
        out[encoded_name] = (
            series.fillna("Unknown").astype(str).map(mapping).astype("float64")
        )
    return out


def drop_incomplete_rows(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    cleaned = df.dropna(subset=FEATURE_COLUMNS + ["target_return"]).reset_index(drop=True)
    print(
        f"Nakon čišćenja NaN (features/target_return): {len(cleaned)} redova "
        f"(uklonjeno {before - len(cleaned)})."
    )
    return cleaned


def train_xgboost(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    *,
    quiet: bool = False,
) -> xgb.XGBRegressor:
    if not quiet:
        print(
            "Treniram XGBRegressor na forward return "
            f"(horizon={HORIZON_DAYS}d, n_estimators=300, max_depth=5)..."
        )
    model = xgb.XGBRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=4,
        objective="reg:squarederror",
        random_state=RANDOM_SEED,
        n_jobs=1,
    )
    model.fit(X_train, y_train)
    return model


def _signed_return(returns: np.ndarray, *, hold_band: float) -> np.ndarray:
    """+1 up, -1 down, 0 flat within hold_band on return units."""
    out = np.zeros(len(returns), dtype=int)
    out[returns > hold_band] = 1
    out[returns < -hold_band] = -1
    return out


def _signed_move(future: np.ndarray, spot: np.ndarray, *, hold_band: float) -> np.ndarray:
    """+1 up, -1 down, 0 flat within hold_band (fraction of spot)."""
    spot_safe = np.where(spot > 0, spot, np.nan)
    change = (future - spot) / spot_safe
    return _signed_return(change, hold_band=hold_band)


def conformal_abs_quantile(
    residuals: np.ndarray,
    *,
    alpha: float = CONFORMAL_ALPHA,
) -> float:
    """Split-conformal absolute residual quantile (finite-sample corrected)."""
    abs_res = np.abs(np.asarray(residuals, dtype=float))
    abs_res = abs_res[np.isfinite(abs_res)]
    n = int(abs_res.size)
    if n <= 0:
        return float("nan")
    level = min(1.0, max(0.0, (1.0 - float(alpha)) * (1.0 + 1.0 / n)))
    try:
        return float(np.quantile(abs_res, level, method="higher"))
    except TypeError:
        return float(np.quantile(abs_res, level, interpolation="higher"))


def evaluate_model(
    model: xgb.XGBRegressor,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    *,
    spot: pd.Series | None = None,
    hold_band: float | None = None,
    target_kind: str = "return",
    conformal_alpha: float = CONFORMAL_ALPHA,
) -> dict[str, float]:
    """Score return (preferred) or price models vs a naive baseline.

    For returns, naive = 0% move. Prefer direction_accuracy and rmse_vs_naive.
    Also fits a split-conformal absolute residual quantile on the holdout.
    """
    band = float(RETURN_HOLD_BAND if hold_band is None else hold_band)
    predictions = np.asarray(model.predict(X_test), dtype=float)
    y = np.asarray(y_test, dtype=float)
    rmse = float(np.sqrt(mean_squared_error(y, predictions)))
    r2 = float(r2_score(y, predictions)) if len(y) > 1 else float("nan")

    metrics: dict[str, float] = {
        "rmse": rmse,
        "r2": r2,
        "horizon_days": float(HORIZON_DAYS),
    }
    if target_kind == "return":
        q = conformal_abs_quantile(y - predictions, alpha=conformal_alpha)
        if q == q:  # not NaN
            metrics["conformal_q"] = float(q)
            metrics["conformal_alpha"] = float(conformal_alpha)
            metrics["conformal_width_cap"] = float(CONFORMAL_WIDTH_CAP)
            print(
                f"Conformal ±q: {q:.4f} "
                f"({int((1 - conformal_alpha) * 100)}% PI on holdout |residual|)"
            )
    print()
    print(f"=== Evaluacija (holdout, target={target_kind}, horizon={HORIZON_DAYS}d) ===")
    print(f"RMSE: {rmse:.6f}")
    print(f"R2:   {r2:.4f}")

    if target_kind == "return":
        naive = np.zeros_like(y)
        naive_rmse = float(np.sqrt(mean_squared_error(y, naive)))
        metrics["naive_rmse"] = naive_rmse
        metrics["rmse_vs_naive"] = float(rmse / naive_rmse) if naive_rmse > 0 else float("nan")
        actual_dir = _signed_return(y, hold_band=band)
        pred_dir = _signed_return(predictions, hold_band=band)
    elif spot is not None and len(spot) == len(y):
        spot_arr = np.asarray(spot, dtype=float)
        naive = spot_arr.copy()
        naive_rmse = float(np.sqrt(mean_squared_error(y, naive)))
        metrics["naive_rmse"] = naive_rmse
        metrics["rmse_vs_naive"] = float(rmse / naive_rmse) if naive_rmse > 0 else float("nan")
        actual_dir = _signed_move(y, spot_arr, hold_band=band)
        pred_dir = _signed_move(predictions, spot_arr, hold_band=band)
    else:
        print("Skipped direction/naive metrics (no spot / unsupported target).")
        return metrics

    movable = actual_dir != 0
    if movable.any():
        direction_acc = float((actual_dir[movable] == pred_dir[movable]).mean() * 100.0)
    else:
        direction_acc = float("nan")
    metrics["direction_accuracy_pct"] = direction_acc
    metrics["direction_n"] = float(int(movable.sum()))
    metrics["pred_flat_pct"] = float((pred_dir == 0).mean() * 100.0)

    print(f"Naive RMSE (0% return / persistence): {naive_rmse:.6f}")
    print(f"RMSE / naive: {metrics['rmse_vs_naive']:.3f}  (<1 = beats baseline)")
    if movable.any():
        print(
            f"Direction accuracy: {direction_acc:.1f}% "
            f"on {int(movable.sum())} non-flat rows (±{band * 100:.2f}% band)"
        )
    print(f"Predicted flat: {metrics['pred_flat_pct']:.1f}% of test rows")
    if metrics["rmse_vs_naive"] >= 0.98:
        print(
            "Napomena: model je blizu naivnog baselinea — "
            "signal smjera još nije dovoljno jak."
        )
    return metrics


def _normalize(values: np.ndarray) -> np.ndarray:
    total = float(values.sum())
    if total <= 0:
        return np.zeros_like(values, dtype=float)
    return values / total


def print_feature_importance(model: xgb.XGBRegressor, feature_names: list[str]) -> pd.DataFrame:
    booster = model.get_booster()
    gain_raw = booster.get_score(importance_type="gain")
    weight_raw = booster.get_score(importance_type="weight")
    gain = np.array([float(gain_raw.get(name, 0.0)) for name in feature_names], dtype=float)
    weight = np.array([float(weight_raw.get(name, 0.0)) for name in feature_names], dtype=float)
    ranked = (
        pd.DataFrame(
            {
                "feature": feature_names,
                "label": [FEATURE_LABELS.get(name, name) for name in feature_names],
                "gain": _normalize(gain),
                "weight": _normalize(weight),
            }
        )
        .sort_values("gain", ascending=False)
        .reset_index(drop=True)
    )

    print()
    print("=== Feature Importance (što AI smatra najvažnijim) ===")
    print(f"{'#':<4}{'Značajka':<24}{'Gain':>10}{'Weight':>10}  Graf (gain)")
    bar_width = 24
    max_gain = float(ranked["gain"].max()) if not ranked.empty else 0.0
    for i, row in ranked.iterrows():
        filled = 0 if max_gain == 0 else int(round(row["gain"] / max_gain * bar_width))
        bar = "█" * filled + "░" * (bar_width - filled)
        print(f"{i + 1:<4}{row['label']:<24}{row['gain']:>9.1%}{row['weight']:>9.1%}  {bar}")

    top = ranked.iloc[0]
    print(f"Najjači signal: {top['label']} (gain {top['gain']:.1%}).")
    if ranked.loc[ranked["feature"] == "supertype_encoded", "gain"].eq(0).all():
        print("Napomena: svi redovi imaju isti supertype, pa ta značajka nema varijacije.")
    return ranked


def maybe_plot_feature_importance(ranked: pd.DataFrame) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Graf preskočen (matplotlib nije instaliran). Tekstualni prikaz je iznad.")
        return

    chart = ranked.sort_values("gain", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(chart["label"], chart["gain"], color="#3b82f6")
    ax.set_xlabel("Gain (normalizirano)")
    ax.set_title("XGBoost feature importance")
    fig.tight_layout()
    output_path = "feature_importance.png"
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    print(f"Graf spremljen u {output_path}.")


def split_features(
    df: pd.DataFrame,
    *,
    return_spot: bool = False,
    time_based: bool = True,
) -> tuple:
    """Train/test split on target_return. Prefer temporal holdout (no shuffle leak)."""
    if "target_return" not in df.columns:
        raise ValueError("split_features requires target_return (run add_time_features)")
    X = df[FEATURE_COLUMNS]
    y = df["target_return"]
    print(
        f"Dijelim podatke: {int((1 - TEST_SIZE) * 100)}% train / {int(TEST_SIZE * 100)}% test "
        f"({'time-based' if time_based and 'date' in df.columns else 'random'})..."
    )

    if time_based and "date" in df.columns and df["date"].nunique() >= 5:
        ordered = df.sort_values("date")
        dates = np.sort(pd.to_datetime(ordered["date"]).unique())
        cut_idx = max(1, int(len(dates) * (1.0 - TEST_SIZE)))
        cut_idx = min(cut_idx, len(dates) - 1)
        cut = dates[cut_idx]
        train_mask = pd.to_datetime(df["date"]) < cut
        test_mask = ~train_mask
        if int(test_mask.sum()) < 10 or int(train_mask.sum()) < 20:
            # Fall back if history is too short for a clean temporal cut.
            time_based = False
        else:
            X_train, X_test = X.loc[train_mask], X.loc[test_mask]
            y_train, y_test = y.loc[train_mask], y.loc[test_mask]
            print(
                f"Train: {len(X_train)} redova | Test: {len(X_test)} redova "
                f"(cut date {pd.Timestamp(cut).date()})."
            )
            if return_spot:
                return X_train, X_test, y_train, y_test, df.loc[test_mask, "price"]
            return X_train, X_test, y_train, y_test

    if return_spot:
        if "price" not in df.columns:
            raise ValueError("split_features(return_spot=True) requires a 'price' column")
        X_train, X_test, y_train, y_test, _spot_train, spot_test = train_test_split(
            X,
            y,
            df["price"],
            test_size=TEST_SIZE,
            random_state=RANDOM_SEED,
        )
        print(f"Train: {len(X_train)} redova | Test: {len(X_test)} redova.")
        return X_train, X_test, y_train, y_test, spot_test
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
    )
    print(f"Train: {len(X_train)} redova | Test: {len(X_test)} redova.")
    return X_train, X_test, y_train, y_test


def card_forecasts(
    model: xgb.XGBRegressor,
    featured: pd.DataFrame,
    *,
    conformal_q: float | None = None,
    hold_band: float | None = None,
    width_cap: float | None = None,
) -> pd.DataFrame:
    """Latest row per card: predict horizon return → target price + PI."""
    band = float(RETURN_HOLD_BAND if hold_band is None else hold_band)
    cap = float(CONFORMAL_WIDTH_CAP if width_cap is None else width_cap)
    latest = (
        featured.sort_values(["card_id", "date"])
        .groupby("card_id", as_index=False)
        .tail(1)
        .dropna(subset=FEATURE_COLUMNS)
        .copy()
    )
    pred_ret = np.asarray(model.predict(latest[FEATURE_COLUMNS]), dtype=float)
    latest["predicted_return"] = pred_ret
    spot = latest["price"].astype(float)
    latest["predicted_price"] = spot * (1.0 + pred_ret)
    latest["id"] = latest["card_id"]
    latest["name_length"] = latest["name"].str.len().astype(int)
    latest["target_price"] = latest["predicted_price"]
    mkt = pd.to_numeric(latest.get("market_price"), errors="coerce").fillna(spot)
    latest["growth"] = latest["predicted_price"] - mkt
    latest["growth_pct"] = np.where(mkt > 0, latest["growth"] / mkt * 100.0, 0.0)
    latest["expected_change_pct"] = pred_ret * 100.0
    if "ret_7" in latest.columns:
        latest["price_change_7d_pct"] = (
            pd.to_numeric(latest["ret_7"], errors="coerce") * 100.0
        )
    q = float(conformal_q) if conformal_q is not None and np.isfinite(float(conformal_q)) else float("nan")
    if q == q and q >= 0:
        latest["pred_lo"] = pred_ret - q
        latest["pred_hi"] = pred_ret + q
        latest["pred_lo_pct"] = latest["pred_lo"] * 100.0
        latest["pred_hi_pct"] = latest["pred_hi"] * 100.0
        width = latest["pred_hi"] - latest["pred_lo"]
        crosses_zero = (latest["pred_lo"] < 0.0) & (latest["pred_hi"] > 0.0)
        too_wide = width > cap
        latest["conformal_ok"] = ~(crosses_zero | too_wide)
    else:
        latest["pred_lo"] = np.nan
        latest["pred_hi"] = np.nan
        latest["pred_lo_pct"] = np.nan
        latest["pred_hi_pct"] = np.nan
        latest["conformal_ok"] = True
    latest["signal"] = np.where(
        pred_ret > band,
        "KUPI",
        np.where(pred_ret < -band, "PRODAJ/ČEKAJ", "HOLD"),
    )
    return latest.reset_index(drop=True)


def fit_predictor() -> tuple[xgb.XGBRegressor, pd.DataFrame]:
    """Trenira model na povijesti i vraća predikciju sljedećeg dana po karti."""
    history = load_history()
    featured, _encoders = add_time_features(history)
    trainable = drop_incomplete_rows(featured)
    X_train, _X_test, y_train, _y_test = split_features(trainable)
    model = train_xgboost(X_train, y_train)
    return model, card_forecasts(model, featured)


def retrain_model(
    *,
    horizon_days: int | None = None,
    artifact_id: str | None = None,
) -> dict[str, float | int]:
    """Ponovno trenira XGBoost na cijelom price_history. Za nightly_update.

    Persists the artifact to Supabase / local disk so Streamlit can skip retrain.
    Use horizon_days=30 + artifact latest_30d for portfolio-native outlook.
    """
    horizon = int(horizon_days if horizon_days is not None else HORIZON_DAYS)
    art_id = artifact_id or (
        ARTIFACT_ID_7D if horizon == int(HORIZON_DAYS) else f"latest_{horizon}d"
    )
    hold_band = (
        float(PORTFOLIO_SIGNAL_BAND)
        if horizon >= int(PORTFOLIO_HORIZON_DAYS)
        else float(RETURN_HOLD_BAND)
    )
    width_cap = (
        float(PORTFOLIO_CONFORMAL_WIDTH_CAP)
        if horizon >= int(PORTFOLIO_HORIZON_DAYS)
        else float(CONFORMAL_WIDTH_CAP)
    )

    history = load_history()
    featured, _encoders = add_time_features(history, horizon_days=horizon)
    trainable = drop_incomplete_rows(featured)
    if len(trainable) < 20:
        raise RuntimeError(f"Premalo redova za trening ({len(trainable)}).")

    X_train, X_test, y_train, y_test, spot_test = split_features(
        trainable, return_spot=True
    )
    model = train_xgboost(X_train, y_train)
    eval_metrics = evaluate_model(
        model,
        X_test,
        y_test,
        spot=spot_test,
        target_kind="return",
        hold_band=hold_band,
    )
    # Override width cap stored for inference gating on this horizon.
    if "conformal_q" in eval_metrics:
        eval_metrics["conformal_width_cap"] = float(width_cap)
    metrics: dict[str, float | int] = {
        "rows": int(len(trainable)),
        "cards": int(history["card_id"].nunique()),
        "rmse": float(eval_metrics["rmse"]),
        "r2": float(eval_metrics["r2"]),
        "horizon_days": int(horizon),
        "target": "return",
        "hold_band": float(hold_band),
    }
    for key in (
        "naive_rmse",
        "rmse_vs_naive",
        "direction_accuracy_pct",
        "direction_n",
        "pred_flat_pct",
        "conformal_q",
        "conformal_alpha",
        "conformal_width_cap",
    ):
        if key in eval_metrics and eval_metrics[key] == eval_metrics[key]:  # not NaN
            metrics[key] = float(eval_metrics[key])

    try:
        from services.walk_forward import walk_forward_evaluate, walk_forward_summary_metrics

        wf = walk_forward_evaluate(
            trainable,
            n_folds=4,
            hold_band=hold_band,
            quiet=True,
        )
        metrics.update(walk_forward_summary_metrics(wf))
        if not wf.get("wf_skipped"):
            print(
                f"Walk-forward ({metrics.get('wf_folds')} folds): "
                f"dir={metrics.get('wf_direction_accuracy_pct', float('nan')):.1f}% "
                f"rmse/naive={metrics.get('wf_rmse_vs_naive', float('nan')):.3f}"
            )
    except Exception as exc:
        print(f"Walk-forward skipped: {exc}", file=sys.stderr)
        metrics["wf_folds"] = 0

    try:
        from services.model_store import save_model_artifact

        save_model_artifact(
            model,
            metrics=metrics,
            feature_columns=list(FEATURE_COLUMNS),
            artifact_id=art_id,
        )
    except Exception as exc:
        print(f"Model artifact save failed ({art_id}): {exc}", file=sys.stderr)
    return metrics


def main() -> int:
    print("=== TCG Market: XGBoost time-series model ===")
    try:
        history = load_history()
        featured, _encoders = add_time_features(history)
        trainable = drop_incomplete_rows(featured)
        if len(trainable) < 20:
            print("Premalo redova za train/test split.", file=sys.stderr)
            return 1

        X_train, X_test, y_train, y_test, spot_test = split_features(
            trainable, return_spot=True
        )
        model = train_xgboost(X_train, y_train)
        eval_metrics = evaluate_model(
            model, X_test, y_test, spot=spot_test, target_kind="return"
        )
        r2 = float(eval_metrics.get("r2") or 0.0)
        vs = float(eval_metrics.get("rmse_vs_naive") or 1.0)
        if vs < 0.95:
            print("Model bije naivni 0% return baseline (rmse/naive < 0.95).")
        if r2 > 0.20:
            print(f"R2 na returnima je {r2:.2f} (na returnima je niži R2 normalan).")

        ranked = print_feature_importance(model, FEATURE_COLUMNS)
        maybe_plot_feature_importance(ranked)
        print("Gotovo.")
        return 0
    except FileNotFoundError as exc:
        print(f"Baza nije pronađena: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Neočekivana greška: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

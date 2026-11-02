# pip install xgboost scikit-learn
# pip install matplotlib   # opcionalno, za graf feature importance
"""XGBoost predikcija sljedeće dnevne cijene iz price_history."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from database import load_history_frame

RANDOM_SEED = 42
TEST_SIZE = 0.2
LAG_FEATURES = ["price_lag_1", "price_lag_3", "price_lag_7", "rolling_mean_7"]
FEATURE_COLUMNS = LAG_FEATURES + ["rarity_encoded", "supertype_encoded"]
FEATURE_LABELS = {
    "price_lag_1": "cijena jučer",
    "price_lag_3": "cijena prije 3 dana",
    "price_lag_7": "cijena prije 7 dana",
    "rolling_mean_7": "7-dnevni prosjek",
    "rarity_encoded": "rijetkost (rarity)",
    "supertype_encoded": "supertype",
}


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


def add_time_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, LabelEncoder]]:
    """Lagovi i 7-dnevni prosjek računaju se posebno za svaku kartu."""
    print("Feature engineering: lagovi po card_id + LabelEncoder (rarity, supertype)...")
    featured = df.sort_values(["card_id", "date"]).reset_index(drop=True)
    price = featured.groupby("card_id", sort=False)["price"]
    featured["price_lag_1"] = price.shift(1)
    featured["price_lag_3"] = price.shift(3)
    featured["price_lag_7"] = price.shift(7)
    featured["rolling_mean_7"] = price.transform(lambda series: series.rolling(7, min_periods=7).mean())
    featured["target_price"] = price.shift(-1)

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
    cleaned = df.dropna(subset=FEATURE_COLUMNS + ["target_price"]).reset_index(drop=True)
    print(f"Nakon čišćenja NaN (lag/target): {len(cleaned)} redova (uklonjeno {before - len(cleaned)}).")
    return cleaned


def train_xgboost(X_train: pd.DataFrame, y_train: pd.Series) -> xgb.XGBRegressor:
    print(
        "Treniram XGBRegressor "
        "(n_estimators=200, learning_rate=0.05, max_depth=6, subsample=0.8)..."
    )
    model = xgb.XGBRegressor(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        objective="reg:squarederror",
        random_state=RANDOM_SEED,
        n_jobs=1,
    )
    model.fit(X_train, y_train)
    return model


def _signed_move(future: np.ndarray, spot: np.ndarray, *, hold_band: float) -> np.ndarray:
    """+1 up, -1 down, 0 flat within hold_band (fraction of spot)."""
    spot_safe = np.where(spot > 0, spot, np.nan)
    change = (future - spot) / spot_safe
    out = np.zeros(len(change), dtype=int)
    out[change > hold_band] = 1
    out[change < -hold_band] = -1
    return out


def evaluate_model(
    model: xgb.XGBRegressor,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    *,
    spot: pd.Series | None = None,
    hold_band: float = 0.0035,
) -> dict[str, float]:
    """Level metrics + direction vs naive (tomorrow = today) baseline.

    High R² alone is misleading: copying today's price often looks “accurate”.
    Prefer direction_accuracy and rmse_vs_naive (< 1 means model beats persistence).
    """
    predictions = np.asarray(model.predict(X_test), dtype=float)
    y = np.asarray(y_test, dtype=float)
    rmse = float(np.sqrt(mean_squared_error(y, predictions)))
    r2 = float(r2_score(y, predictions))

    metrics: dict[str, float] = {"rmse": rmse, "r2": r2}
    print()
    print("=== Evaluacija na testnom skupu (20%) ===")
    print(f"RMSE: {rmse:.4f}")
    print(f"R2:   {r2:.4f}")

    if spot is not None and len(spot) == len(y):
        spot_arr = np.asarray(spot, dtype=float)
        naive = spot_arr.copy()
        naive_rmse = float(np.sqrt(mean_squared_error(y, naive)))
        metrics["naive_rmse"] = naive_rmse
        metrics["rmse_vs_naive"] = float(rmse / naive_rmse) if naive_rmse > 0 else float("nan")

        actual_dir = _signed_move(y, spot_arr, hold_band=hold_band)
        pred_dir = _signed_move(predictions, spot_arr, hold_band=hold_band)
        movable = actual_dir != 0
        if movable.any():
            direction_acc = float((actual_dir[movable] == pred_dir[movable]).mean() * 100.0)
        else:
            direction_acc = float("nan")
        metrics["direction_accuracy_pct"] = direction_acc
        metrics["direction_n"] = float(int(movable.sum()))
        # How often model predicts a flat day (persistence trap symptom).
        metrics["pred_flat_pct"] = float((pred_dir == 0).mean() * 100.0)

        print(f"Naive RMSE (tomorrow=today): {naive_rmse:.4f}")
        print(f"RMSE / naive: {metrics['rmse_vs_naive']:.3f}  (<1 = beats persistence)")
        if movable.any():
            print(
                f"Direction accuracy: {direction_acc:.1f}% "
                f"on {int(movable.sum())} non-flat days (±{hold_band * 100:.2f}% band)"
            )
        print(f"Predicted flat (HOLD): {metrics['pred_flat_pct']:.1f}% of test rows")
        if metrics["rmse_vs_naive"] >= 0.98:
            print(
                "Napomena: model je blizu naivnog baselinea — "
                "visoki R2 ne znači koristan signal smjera."
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
) -> tuple:
    X = df[FEATURE_COLUMNS]
    y = df["target_price"]
    print(f"Dijelim podatke: {int((1 - TEST_SIZE) * 100)}% train / {int(TEST_SIZE * 100)}% test...")
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


def card_forecasts(model: xgb.XGBRegressor, featured: pd.DataFrame) -> pd.DataFrame:
    """Zadnji dan svake karte: predviđa cijenu sljedećeg dana."""
    latest = (
        featured.sort_values(["card_id", "date"])
        .groupby("card_id", as_index=False)
        .tail(1)
        .dropna(subset=FEATURE_COLUMNS)
        .copy()
    )
    latest["predicted_price"] = model.predict(latest[FEATURE_COLUMNS])
    latest["id"] = latest["card_id"]
    latest["name_length"] = latest["name"].str.len().astype(int)
    latest["target_price"] = latest["predicted_price"]
    latest["growth"] = latest["predicted_price"] - latest["market_price"]
    latest["growth_pct"] = latest["growth"] / latest["market_price"] * 100.0
    latest["signal"] = np.where(
        latest["predicted_price"] > latest["market_price"],
        "KUPI",
        "PRODAJ/ČEKAJ",
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


def retrain_model() -> dict[str, float | int]:
    """Ponovno trenira XGBoost na cijelom price_history. Za nightly_update.

    Persists the artifact to Supabase / local disk so Streamlit can skip retrain.
    """
    history = load_history()
    featured, _encoders = add_time_features(history)
    trainable = drop_incomplete_rows(featured)
    if len(trainable) < 20:
        raise RuntimeError(f"Premalo redova za trening ({len(trainable)}).")

    X_train, X_test, y_train, y_test, spot_test = split_features(
        trainable, return_spot=True
    )
    model = train_xgboost(X_train, y_train)
    eval_metrics = evaluate_model(model, X_test, y_test, spot=spot_test)
    metrics: dict[str, float | int] = {
        "rows": int(len(trainable)),
        "cards": int(history["card_id"].nunique()),
        "rmse": float(eval_metrics["rmse"]),
        "r2": float(eval_metrics["r2"]),
    }
    for key in (
        "naive_rmse",
        "rmse_vs_naive",
        "direction_accuracy_pct",
        "direction_n",
        "pred_flat_pct",
    ):
        if key in eval_metrics and eval_metrics[key] == eval_metrics[key]:  # not NaN
            metrics[key] = float(eval_metrics[key])

    try:
        from services.model_store import save_model_artifact

        save_model_artifact(model, metrics=metrics, feature_columns=list(FEATURE_COLUMNS))
    except Exception as exc:
        print(f"Model artifact save failed: {exc}", file=sys.stderr)
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
        eval_metrics = evaluate_model(model, X_test, y_test, spot=spot_test)
        r2 = float(eval_metrics["r2"])
        if r2 > 0.80:
            print("R2 je iznad 0.80 (provjeri i RMSE/naive + direction accuracy).")

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

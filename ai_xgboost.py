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


def load_history() -> pd.DataFrame:
    print("Učitavam price_history spojenu s cards (Supabase)...")
    df = load_history_frame()
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


def evaluate_model(model: xgb.XGBRegressor, X_test: pd.DataFrame, y_test: pd.Series) -> tuple[float, float]:
    predictions = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, predictions)))
    r2 = float(r2_score(y_test, predictions))
    print()
    print("=== Evaluacija na testnom skupu (20%) ===")
    print(f"RMSE: {rmse:.4f}")
    print(f"R2:   {r2:.4f}")
    return rmse, r2


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


def split_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    X = df[FEATURE_COLUMNS]
    y = df["target_price"]
    print(f"Dijelim podatke: {int((1 - TEST_SIZE) * 100)}% train / {int(TEST_SIZE * 100)}% test...")
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
    """Ponovno trenira XGBoost na cijelom price_history. Za nightly_update."""
    history = load_history()
    featured, _encoders = add_time_features(history)
    trainable = drop_incomplete_rows(featured)
    if len(trainable) < 20:
        raise RuntimeError(f"Premalo redova za trening ({len(trainable)}).")

    X_train, X_test, y_train, y_test = split_features(trainable)
    model = train_xgboost(X_train, y_train)
    rmse, r2 = evaluate_model(model, X_test, y_test)
    return {
        "rows": int(len(trainable)),
        "cards": int(history["card_id"].nunique()),
        "rmse": float(rmse),
        "r2": float(r2),
    }


def main() -> int:
    print("=== TCG Market: XGBoost time-series model ===")
    try:
        history = load_history()
        featured, _encoders = add_time_features(history)
        trainable = drop_incomplete_rows(featured)
        if len(trainable) < 20:
            print("Premalo redova za train/test split.", file=sys.stderr)
            return 1

        X_train, X_test, y_train, y_test = split_features(trainable)
        model = train_xgboost(X_train, y_train)
        _rmse, r2 = evaluate_model(model, X_test, y_test)
        if r2 > 0.80:
            print("R2 je iznad 0.80.")
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

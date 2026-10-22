# pip install scikit-learn
"""Predviđanje 7-dnevnog rasta cijena TCG karata (Linear Regression)."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import LabelEncoder

from database import engine

HISTORY_DAYS = 7
FORECAST_DAYS = 7
TOP_N = 5
RANDOM_SEED = 42

# Viši score = rjeđa karta i jači očekivani drift u simulaciji.
RARITY_SCORES = {
    "Common": 1,
    "Uncommon": 2,
    "Rare": 3,
    "Rare Holo": 4,
    "Double Rare": 5,
    "Ultra Rare": 6,
    "Illustration Rare": 6,
    "Special Illustration Rare": 7,
    "Hyper Rare": 8,
    "Secret Rare": 8,
}


def load_cards() -> pd.DataFrame:
    print("Učitavam karte iz tablice 'cards'...")
    df = pd.read_sql("SELECT * FROM cards", engine)
    print(f"Učitano {len(df)} redova.")
    return df


def clean_cards(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    cleaned = df.copy()
    cleaned["market_price"] = pd.to_numeric(cleaned["market_price"], errors="coerce")
    cleaned = cleaned.dropna(subset=["market_price"])
    cleaned = cleaned[cleaned["market_price"] > 0]
    cleaned["rarity"] = cleaned["rarity"].fillna("Unknown")
    cleaned["set_name"] = cleaned["set_name"].fillna("Unknown")
    cleaned["rarity_score"] = cleaned["rarity"].map(RARITY_SCORES).fillna(1).astype(float)
    print(f"Nakon čišćenja: {len(cleaned)} karata (uklonjeno {before - len(cleaned)}).")
    return cleaned.reset_index(drop=True)


def simulate_price_history(
    current_price: float,
    rarity_score: float,
    days: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Simulira povijesni niz koji završava na današnjoj cijeni.

    Rjeđe karte imaju veći dnevni drift i volatilnost, pa model uči
    da rarity utječe na očekivani rast.
    """
    daily_drift = 0.0015 * rarity_score
    daily_vol = 0.008 + 0.006 * rarity_score
    prices = [float(current_price)]
    price = float(current_price)
    for _ in range(days):
        shock = float(rng.normal(0.0, daily_vol))
        factor = 1.0 + daily_drift + shock
        price = price / max(factor, 0.5)
        price = max(price, 0.01)
        prices.append(price)
    return np.array(list(reversed(prices)), dtype=float)


def build_training_set(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, LabelEncoder]:
    """Gradi (cijena_t, rarity, set) -> cijena_{t+1} iz simulirane povijesti."""
    rng = np.random.default_rng(RANDOM_SEED)
    set_encoder = LabelEncoder()
    set_codes = set_encoder.fit_transform(df["set_name"].astype(str))

    features: list[list[float]] = []
    targets: list[float] = []

    print(f"Simuliram {HISTORY_DAYS} dana povijesti za {len(df)} karata...")
    for row, set_code in zip(df.itertuples(index=False), set_codes):
        history = simulate_price_history(
            current_price=row.market_price,
            rarity_score=row.rarity_score,
            days=HISTORY_DAYS,
            rng=rng,
        )
        for day in range(len(history) - 1):
            features.append(
                [np.log(history[day]), row.rarity_score, float(set_code)]
            )
            targets.append(np.log(history[day + 1]))

    X = np.asarray(features, dtype=float)
    y = np.asarray(targets, dtype=float)
    print(f"Trening skup: {len(X)} prijelaza (dan t -> dan t+1).")
    return X, y, set_encoder


def train_model(X: np.ndarray, y: np.ndarray) -> LinearRegression:
    print("Treniram Linear Regression...")
    model = LinearRegression()
    model.fit(X, y)
    print(
        "Koeficijenti (log-cijena): "
        f"log_price={model.coef_[0]:.4f}, "
        f"rarity={model.coef_[1]:.4f}, "
        f"set={model.coef_[2]:.4f} | "
        f"intercept={model.intercept_:.4f}"
    )
    return model


def forecast_prices(
    df: pd.DataFrame,
    model: LinearRegression,
    set_encoder: LabelEncoder,
    days: int = FORECAST_DAYS,
) -> pd.DataFrame:
    """Predviđa cijenu za idućih `days` dana, korak po korak."""
    set_codes = set_encoder.transform(df["set_name"].astype(str))
    predicted = []

    for row, set_code in zip(df.itertuples(index=False), set_codes):
        log_price = float(np.log(row.market_price))
        for _ in range(days):
            log_price = float(
                model.predict([[log_price, row.rarity_score, float(set_code)]])[0]
            )
        price = max(float(np.exp(log_price)), 0.01)
        predicted.append(price)

    result = df.copy()
    result["predicted_price"] = predicted
    result["predicted_growth"] = result["predicted_price"] - result["market_price"]
    result["predicted_growth_pct"] = (
        result["predicted_growth"] / result["market_price"] * 100.0
    )
    return result


def print_top_growth(df: pd.DataFrame, n: int = TOP_N) -> None:
    top = df.sort_values("predicted_growth_pct", ascending=False).head(n)
    print()
    print(f"=== Top {n} karata s najvećim predviđenim rastom ({FORECAST_DAYS} dana) ===")
    print(
        f"{'#':<4}{'Karta':<28}{'Rarity':<16}"
        f"{'Current':>10}{'Predicted':>12}{'Rast %':>10}"
    )
    for i, row in enumerate(top.itertuples(index=False), start=1):
        name = (row.name or row.id)[:26]
        print(
            f"{i:<4}{name:<28}{str(row.rarity):<16}"
            f"{row.market_price:>10.2f}{row.predicted_price:>12.2f}"
            f"{row.predicted_growth_pct:>9.1f}%"
        )


def main() -> int:
    print("=== TCG Market: AI predikcija cijena ===")
    try:
        cards = load_cards()
        cards = clean_cards(cards)
        if cards.empty:
            print("Nema karata s valjanom cijenom za treniranje.", file=sys.stderr)
            return 1

        X, y, set_encoder = build_training_set(cards)
        model = train_model(X, y)
        forecast = forecast_prices(cards, model, set_encoder)
        print_top_growth(forecast)
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

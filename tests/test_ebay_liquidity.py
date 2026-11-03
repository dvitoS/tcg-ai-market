"""eBay liquidity snapshot stats + as-of feature join."""

from __future__ import annotations

import pandas as pd

from ai_xgboost import FEATURE_COLUMNS
from services.ebay_liquidity import (
    EBAY_FEATURE_COLUMNS,
    attach_ebay_features,
    stats_from_listings,
)


def test_feature_columns_include_ebay():
    for col in EBAY_FEATURE_COLUMNS:
        assert col in FEATURE_COLUMNS


def test_stats_from_listings_premium():
    listings = [{"price": 10.0}, {"price": 12.0}, {"price": 14.0}]
    st = stats_from_listings(listings, spot=10.0)
    assert st["active_n"] == 3
    assert st["ask_median"] == 12.0
    assert abs(float(st["ask_premium"]) - 0.2) < 1e-9


def test_attach_ebay_features_asof_ffill():
    featured = pd.DataFrame(
        [
            {"card_id": "a", "date": "2024-01-01", "price": 10.0},
            {"card_id": "a", "date": "2024-01-05", "price": 11.0},
            {"card_id": "a", "date": "2024-01-10", "price": 12.0},
            {"card_id": "b", "date": "2024-01-05", "price": 5.0},
        ]
    )
    snaps = pd.DataFrame(
        [
            {
                "card_id": "a",
                "snapshot_date": "2024-01-04",
                "active_n": 8,
                "ask_premium": 0.15,
            },
            {
                "card_id": "a",
                "snapshot_date": "2024-01-09",
                "active_n": 3,
                "ask_premium": -0.05,
            },
        ]
    )
    out = attach_ebay_features(featured, snaps)
    # Jan 1: no prior snapshot
    r0 = out.loc[out["date"].astype(str).str.startswith("2024-01-01")].iloc[0]
    assert float(r0["ebay_has_obs"]) == 0.0
    # Jan 5: uses Jan 4 snapshot
    r1 = out.loc[
        (out["card_id"] == "a") & (out["date"].astype(str).str.startswith("2024-01-05"))
    ].iloc[0]
    assert float(r1["ebay_has_obs"]) == 1.0
    assert abs(float(r1["ebay_ask_premium"]) - 0.15) < 1e-9
    assert float(r1["ebay_active_n_log"]) > 0
    # Card b: never observed
    rb = out.loc[out["card_id"] == "b"].iloc[0]
    assert float(rb["ebay_has_obs"]) == 0.0

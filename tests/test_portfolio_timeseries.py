"""Unit tests for portfolio value-vs-cost timeseries."""

from __future__ import annotations

import pandas as pd

from services.portfolio_timeseries import portfolio_timeseries


def test_portfolio_timeseries_empty_inputs() -> None:
    empty = portfolio_timeseries(pd.DataFrame(), pd.DataFrame())
    assert list(empty.columns) == ["date", "invested", "market_value"]
    assert empty.empty


def test_portfolio_timeseries_open_lot_mark_to_market() -> None:
    lots = pd.DataFrame(
        [
            {
                "card_id": "c1",
                "quantity": 2,
                "purchase_price": 10.0,
                "purchase_date": "2024-01-01",
                "status": "open",
                "sale_date": None,
            }
        ]
    )
    history = pd.DataFrame(
        [
            {"card_id": "c1", "date": "2024-01-01", "price": 10.0},
            {"card_id": "c1", "date": "2024-01-02", "price": 12.0},
            {"card_id": "c1", "date": "2024-01-03", "price": 11.0},
        ]
    )
    series = portfolio_timeseries(lots, history, max_days=30)
    assert len(series) == 3
    assert float(series.iloc[0]["invested"]) == 20.0
    assert float(series.iloc[0]["market_value"]) == 20.0
    assert float(series.iloc[1]["market_value"]) == 24.0
    assert float(series.iloc[2]["market_value"]) == 22.0


def test_portfolio_timeseries_sold_lot_stops_after_sale() -> None:
    lots = pd.DataFrame(
        [
            {
                "card_id": "c1",
                "quantity": 1,
                "purchase_price": 5.0,
                "purchase_date": "2024-01-01",
                "status": "sold",
                "sale_date": "2024-01-02",
            }
        ]
    )
    history = pd.DataFrame(
        [
            {"card_id": "c1", "date": "2024-01-01", "price": 5.0},
            {"card_id": "c1", "date": "2024-01-02", "price": 6.0},
            {"card_id": "c1", "date": "2024-01-03", "price": 7.0},
        ]
    )
    series = portfolio_timeseries(lots, history, max_days=30)
    assert len(series) == 3
    assert float(series.iloc[1]["invested"]) == 5.0
    assert float(series.iloc[1]["market_value"]) == 6.0
    # After sale_date the lot drops out (zeros for remaining calendar).
    assert float(series.iloc[2]["invested"]) == 0.0
    assert float(series.iloc[2]["market_value"]) == 0.0

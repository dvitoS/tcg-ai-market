"""Condition / printing NM spot multipliers."""

from __future__ import annotations

from services.lot_price_adjust import (
    adjust_nm_price,
    lot_price_factor,
    normalize_condition,
    normalize_printing,
)


def test_normalize_condition_and_printing() -> None:
    assert normalize_condition("lp") == "LP"
    assert normalize_condition("PSA 10") == "NM"
    assert normalize_printing("reverse holo") == "Reverse"
    assert normalize_printing("Holofoil") == "Holo"


def test_lot_price_factor_lp_reverse() -> None:
    assert abs(lot_price_factor(condition="LP", printing="Reverse") - 0.85 * 1.05) < 1e-9


def test_adjust_nm_price() -> None:
    assert adjust_nm_price(100.0, condition="MP", printing="Normal") == 70.0
    assert adjust_nm_price(None, condition="NM") is None


def test_enrich_lots_applies_factor() -> None:
    from api.portfolio_service import enrich_lots

    rows = enrich_lots(
        [
            {
                "card_id": "__missing__",
                "quantity": 2,
                "purchase_price": 10.0,
                "condition": "LP",
                "printing": "Normal",
                "market_price": 20.0,
                "status": "open",
            }
        ]
    )
    lot = rows[0]
    assert lot["condition"] == "LP"
    assert lot["printing"] == "Normal"
    assert abs(float(lot["price_factor"]) - 0.85) < 1e-9
    # Board miss → falls back to lot.market_price then multiplies.
    assert abs(float(lot["market_price"]) - 17.0) < 1e-9
    assert abs(float(lot["market_value"]) - 34.0) < 1e-9

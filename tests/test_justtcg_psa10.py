"""Unit tests for JustTCG v2 graded helpers (no live API)."""

from __future__ import annotations

from justtcg_psa10 import (
    _format_grade_param,
    _graded_card_params,
    history_points_from_v2_variant,
    pick_psa_variant,
    psa_stats_from_variant,
)


def test_format_grade_param_csv() -> None:
    assert _format_grade_param([10.0]) == "10"
    assert _format_grade_param([9.0, 10.0]) == "9,10"
    assert _format_grade_param([9.5, 10.0]) == "9.5,10"


def test_graded_card_params_match_docs() -> None:
    params = _graded_card_params(grades=[9.0, 10.0])
    assert params["graded"] == "only"
    assert params["grading_company"] == "PSA"
    assert params["grade"] == "9,10"
    assert params["regions"] == "NA"
    assert "periods.90d" in params["include"]
    assert "price_history.90d" in params["include"]


def test_pick_psa_prefers_current_without_qualifier() -> None:
    variants = [
        {
            "type": "graded",
            "grading": {
                "company": "PSA",
                "grade": 10,
                "qualifier": "OC",
                "canonical": "PSA 10 OC",
            },
            "markets": [
                {"region": "NA", "price": 100.0, "price_status": "current"},
            ],
        },
        {
            "type": "graded",
            "grading": {
                "company": "PSA",
                "grade": 10,
                "qualifier": None,
                "canonical": "PSA 10",
            },
            "markets": [
                {"region": "NA", "price": 120.0, "price_status": "current"},
            ],
        },
    ]
    picked = pick_psa_variant(variants, grade=10.0)
    assert picked is not None
    assert picked["grading"]["canonical"] == "PSA 10"
    assert picked["grading"]["qualifier"] is None


def test_expired_uses_last_price() -> None:
    variant = {
        "type": "graded",
        "grading": {"company": "PSA", "grade": 10, "canonical": "PSA 10"},
        "markets": [
            {
                "region": "NA",
                "currency": "USD",
                "price": None,
                "price_status": "expired",
                "last_price": 4550.0,
                "updated_at": 1765630000,
                "last_sale_at": 1765630000,
                "price_expires_at": 1773406000,
                "periods": {"90d": {"sales_count": 1, "avg": 4550.0}},
                "price_history": [],
            }
        ],
    }
    points = history_points_from_v2_variant(variant)
    assert len(points) == 1
    assert points[0]["price"] == 4550.0
    stats = psa_stats_from_variant(variant)
    assert stats["price_status"] == "expired"
    assert stats["price"] == 4550.0
    assert stats["sales_count"] == 1
    assert stats["period_key"] == "90d"
    assert stats["last_sale_at"] == 1765630000


def test_unpriced_has_no_points() -> None:
    variant = {
        "type": "graded",
        "grading": {"company": "PSA", "grade": 10, "canonical": "PSA 10"},
        "markets": [
            {
                "region": "NA",
                "currency": "USD",
                "price": None,
                "price_status": "unpriced",
                "last_price": None,
                "periods": {},
                "price_history": [],
            }
        ],
    }
    assert history_points_from_v2_variant(variant) == []
    stats = psa_stats_from_variant(variant)
    assert stats["price_status"] == "unpriced"
    assert stats["price"] is None

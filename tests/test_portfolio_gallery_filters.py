"""Soft Ink portfolio gallery filter helpers (TS source smoke)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILTERS = ROOT / "web" / "src" / "lib" / "portfolioFilters.ts"


def test_portfolio_filters_module_exports_core_api() -> None:
    text = FILTERS.read_text(encoding="utf-8")
    assert "filterPortfolioLots" in text
    assert "uniqueLotRarities" in text
    assert "value_desc" in text
    assert "pnl_desc" in text

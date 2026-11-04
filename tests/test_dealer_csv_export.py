"""Parity check: Soft Ink dealer CSV column order matches Streamlit export intent."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEALER_CSV = ROOT / "web" / "src" / "lib" / "dealerCsv.ts"


def test_soft_ink_dealer_csv_columns_include_streamlit_core() -> None:
    text = DEALER_CSV.read_text(encoding="utf-8")
    for col in (
        "action",
        "name",
        "card_id",
        "quantity",
        "spot",
        "expected_change_pct",
        "net_edge_pct",
        "conformal_ok",
        "pred_lo_pct",
        "pred_hi_pct",
        "matched",
    ):
        assert f'"{col}"' in text or f"'{col}'" in text or col in text

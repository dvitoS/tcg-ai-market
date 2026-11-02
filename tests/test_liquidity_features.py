"""Liquidity proxy features for detail/inference feature frames."""

from __future__ import annotations

import numpy as np

from services.forecast import _feature_frame_from_prices


def test_feature_frame_includes_liquidity_cols():
    # 20 days with a real move mid-window so abs/flat/hl are defined.
    prices = [10.0] * 10 + [10.0 + i * 0.2 for i in range(10)]
    frame = _feature_frame_from_prices(prices, 1.0, 0.0, set_ret_7=0.01)
    assert frame is not None
    row = frame.iloc[0]
    assert "mean_abs_ret_7" in frame.columns
    assert "flat_share_14" in frame.columns
    assert "hl_range_14" in frame.columns
    assert np.isfinite(row["mean_abs_ret_7"])
    assert 0.0 <= float(row["flat_share_14"]) <= 1.0
    assert float(row["hl_range_14"]) > 0.0

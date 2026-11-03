"""Align prediction frames to persisted model feature schemas."""

from __future__ import annotations

import pandas as pd

from services.forecast import align_features_for_model, model_feature_names


class _FakeModel:
    feature_names_in_ = ["ret_1", "ret_7", "log_price"]

    def get_booster(self):
        raise RuntimeError("unused")


def test_align_pads_missing_and_drops_extra():
    frame = pd.DataFrame(
        [{"ret_1": 0.1, "ret_7": 0.2, "ebay_has_obs": 1.0, "extra": 9.0}]
    )
    aligned = align_features_for_model(frame, _FakeModel())
    assert list(aligned.columns) == ["ret_1", "ret_7", "log_price"]
    assert float(aligned.loc[0, "log_price"]) == 0.0
    assert "ebay_has_obs" not in aligned.columns


def test_model_feature_names_fallback():
    class _Bare:
        pass

    names = model_feature_names(_Bare())
    assert "ret_1" in names

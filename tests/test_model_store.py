"""Round-trip encode/decode for model artifacts (no network)."""

from __future__ import annotations

from services.model_store import _decode_model, _encode_model


def test_encode_decode_roundtrip():
    payload = {"hello": [1, 2, 3], "ok": True}
    blob = _encode_model(payload)
    assert isinstance(blob, str)
    assert len(blob) > 10
    assert _decode_model(blob) == payload

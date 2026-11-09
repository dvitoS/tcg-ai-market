"""API runtime stays lean — no Streamlit, no full-board rebuild on 512MB."""

from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_api_runtime_requirements_omit_streamlit():
    text = (ROOT / "requirements-api-runtime.txt").read_text(encoding="utf-8")
    assert "streamlit" not in text.lower()  # package pin must stay out of runtime
    assert "requirements-api.txt" in text
    assert "xgboost" in text.lower()
    assert "pandas" in text.lower()


def test_dockerfile_api_uses_runtime_requirements_and_service_flag():
    text = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")
    assert "requirements-api-runtime.txt" in text
    assert "KESTREL_SERVICE=api" in text
    assert "WEB_CONCURRENCY=1" in text
    assert "MALLOC_ARENA_MAX=2" in text
    # Must not install the Streamlit-heavy root requirements.txt
    assert "pip install --no-cache-dir -r requirements.txt" not in text
    assert "pip install --no-cache-dir -r requirements-api-runtime.txt" in text


def test_build_market_board_blocked_in_api_process(monkeypatch):
    import services.exchange as exchange

    monkeypatch.setenv("KESTREL_SERVICE", "api")

    with pytest.raises(RuntimeError, match="disabled in the API process"):
        exchange.build_market_board(persist=False, history=None)


def test_build_market_board_guard_skips_when_history_provided(monkeypatch):
    """Preloaded history bypasses the API catalog-wide pull guard."""
    import pandas as pd

    import services.exchange as exchange

    monkeypatch.setenv("KESTREL_SERVICE", "api")
    hist = pd.DataFrame({"card_id": ["a"], "price": [1.0]})

    def boom_features(*_a, **_k):
        raise RuntimeError("passed-guard")

    monkeypatch.setattr(exchange, "add_time_features", boom_features)

    with pytest.raises(RuntimeError, match="passed-guard"):
        exchange.build_market_board(persist=False, history=hist)


def test_explain_service_avoids_ai_xgboost_import():
    import ast

    tree = ast.parse((ROOT / "api/explain_service.py").read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert "ai_xgboost" not in mods

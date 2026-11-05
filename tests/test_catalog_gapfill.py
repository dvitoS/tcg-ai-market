"""Catalog gap-fill selection + pokemontcg pacing helpers."""

from __future__ import annotations

import importlib


def test_rate_limit_sleep_fast_with_api_key(monkeypatch):
    import config

    config = importlib.reload(config)
    monkeypatch.setattr(config, "_secret", lambda name, default="": "")
    monkeypatch.setenv("POKEMONTCG_API_KEY", "test-key")
    monkeypatch.delenv("POKEMONTCG_RATE_SLEEP", raising=False)
    assert config.pokemon_tcg_api_key() == "test-key"
    assert config.rate_limit_sleep_seconds() == config.RATE_LIMIT_SLEEP_SECONDS_WITH_KEY


def test_rate_limit_sleep_slow_without_key(monkeypatch):
    import config

    config = importlib.reload(config)
    monkeypatch.setattr(config, "_secret", lambda name, default="": "")
    monkeypatch.delenv("POKEMONTCG_API_KEY", raising=False)
    monkeypatch.delenv("POKEMON_TCG_API_KEY", raising=False)
    monkeypatch.delenv("POKEMONTCG_RATE_SLEEP", raising=False)
    assert config.pokemon_tcg_api_key() == ""
    assert config.rate_limit_sleep_seconds() == config.RATE_LIMIT_SLEEP_SECONDS


def test_select_gapfill_prefers_missing_then_incomplete(monkeypatch):
    import pokemon_tcg_client as ptcg

    rows = [
        {"id": "sv8", "name": "Surging Sparks", "total": 100},
        {"id": "base1", "name": "Base", "total": 102},
        {"id": "sv3pt5", "name": "151", "total": 207},
        {"id": "me1", "name": "Mega Evolution", "total": 50},
    ]
    db_counts = {
        "sv8": 100,  # complete
        "base1": 40,  # incomplete
        # sv3pt5 missing
        "me1": 50,  # complete
    }
    selected, stats = ptcg.select_gapfill_catalog_targets(
        budget=10,
        db_counts=db_counts,
        set_rows=rows,
    )
    assert stats["api_sets"] == 4
    assert stats["complete"] == 2
    assert stats["missing"] == 1
    assert stats["incomplete"] == 1
    assert [sid for sid, _ in selected] == ["sv3pt5", "base1"]


def test_select_gapfill_respects_budget(monkeypatch):
    import pokemon_tcg_client as ptcg

    rows = [
        {"id": f"s{i}", "name": f"Set {i}", "total": 10}
        for i in range(8)
    ]
    selected, stats = ptcg.select_gapfill_catalog_targets(
        budget=3,
        db_counts={},
        set_rows=rows,
    )
    assert stats["selected"] == 3
    assert len(selected) == 3
    assert stats["missing"] == 8


def test_select_gapfill_empty_when_complete():
    import pokemon_tcg_client as ptcg

    rows = [{"id": "sv8", "name": "Surging Sparks", "total": 2}]
    selected, stats = ptcg.select_gapfill_catalog_targets(
        budget=40,
        db_counts={"sv8": 2},
        set_rows=rows,
    )
    assert selected == []
    assert stats["complete"] == 1
    assert stats["selected"] == 0

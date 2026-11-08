"""Phase C3 — nightly SLO + board TTL cache."""

from __future__ import annotations

import time

import pandas as pd
from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache, load_board
from api.main import app
from services.nightly_slo import PhaseTimer, evaluate_nightly_slo


def test_evaluate_nightly_slo_ok() -> None:
    result = evaluate_nightly_slo(
        elapsed_s=120.0,
        max_seconds=9000,
        quotes_written=42,
        failures=[],
    )
    assert result["slo_ok"] is True
    assert result["slo_reasons"] == []
    assert result["quotes_written"] == 42


def test_evaluate_nightly_slo_quotes_gate() -> None:
    result = evaluate_nightly_slo(
        elapsed_s=10.0,
        max_seconds=9000,
        quotes_written=0,
        failures=[],
    )
    assert result["slo_ok"] is False
    assert "quotes_not_written" in result["slo_reasons"]


def test_evaluate_nightly_slo_retrain_and_budget() -> None:
    result = evaluate_nightly_slo(
        elapsed_s=10_000.0,
        max_seconds=9000,
        quotes_written=5,
        failures=["retrain", "catalog"],
    )
    assert result["slo_ok"] is False
    assert "retrain_failed" in result["slo_reasons"]
    assert "elapsed_over_budget" in result["slo_reasons"]
    # Catalog failure alone does not fail SLO when quotes refreshed.
    assert "catalog" not in result["slo_reasons"]


def test_evaluate_nightly_slo_sure_board_gate() -> None:
    ok = evaluate_nightly_slo(
        elapsed_s=100.0,
        max_seconds=9000,
        quotes_written=40,
        failures=[],
        sure_rows=12,
    )
    assert ok["slo_ok"] is True
    empty = evaluate_nightly_slo(
        elapsed_s=100.0,
        max_seconds=9000,
        quotes_written=40,
        failures=[],
        sure_rows=0,
    )
    assert empty["slo_ok"] is False
    assert "sure_board_empty" in empty["slo_reasons"]


def test_phase_timer_elapsed() -> None:
    timer = PhaseTimer("demo")
    time.sleep(0.02)
    elapsed = timer.finish(ok=True)
    assert elapsed >= 0.01
    assert timer.ok is True
    assert timer.error is None


def test_board_cache_ttl(monkeypatch) -> None:
    clear_board_cache()
    calls = {"n": 0}
    frame = pd.DataFrame(
        [
            {
                "card_id": "sv3-1",
                "name": "Charmander",
                "set_name": "Obsidian Flames",
                "rarity": "Common",
                "price": 1.0,
                "pred_change_pct": 0.0,
                "pred_lo_pct": -2.0,
                "pred_hi_pct": 2.0,
                "confidence": 0.5,
                "image_url": None,
            }
        ]
    )

    def _fake_uncached():
        calls["n"] += 1
        return frame.copy(), "demo"

    monkeypatch.setattr(
        "api.catalog_service._load_board_uncached",
        _fake_uncached,
    )
    monkeypatch.setattr(
        "config.board_cache_ttl_seconds",
        lambda: 0.05,
    )
    monkeypatch.setattr(
        "services.quotes_store.market_quotes_revision",
        lambda: "rev-1",
    )

    b1, s1 = load_board()
    b2, s2 = load_board()
    assert s1 == "demo" and s2 == "demo"
    assert len(b1) == 1 and len(b2) == 1
    assert calls["n"] == 1

    time.sleep(0.06)
    b3, s3 = load_board()
    assert s3 == "demo"
    assert len(b3) == 1
    assert calls["n"] == 2


def test_board_cache_busts_on_quotes_revision(monkeypatch) -> None:
    clear_board_cache()
    calls = {"n": 0}
    rev = {"v": "a"}
    frame = pd.DataFrame(
        [
            {
                "card_id": "sv3-1",
                "name": "Charmander",
                "set_name": "Obsidian Flames",
                "rarity": "Common",
                "price": 1.0,
                "pred_change_pct": 0.0,
                "pred_lo_pct": -2.0,
                "pred_hi_pct": 2.0,
                "confidence": 0.5,
                "image_url": None,
            }
        ]
    )

    def _fake_uncached():
        calls["n"] += 1
        return frame.copy(), "demo"

    monkeypatch.setattr("api.catalog_service._load_board_uncached", _fake_uncached)
    monkeypatch.setattr("config.board_cache_ttl_seconds", lambda: 60.0)
    monkeypatch.setattr(
        "services.quotes_store.market_quotes_revision",
        lambda: rev["v"],
    )

    load_board()
    load_board()
    assert calls["n"] == 1
    rev["v"] = "b"  # heal/quarantine bumped updated_at
    load_board()
    assert calls["n"] == 2
    clear_board_cache()


def test_data_health_includes_nightly_slo(monkeypatch) -> None:
    from services import prices as prices_mod

    prices_mod.reset_justtcg_observability()
    monkeypatch.setattr(
        "services.spot_qa.data_health_spot_fields",
        lambda: {
            "cards_total": 10,
            "cards_with_history": 8,
            "history_coverage_pct": 80.0,
            "fresh_history_pct": 50.0,
            "sure_rows": 4,
            "quotes_total": 9,
            "unmatched_sets_count": 0,
            "unmatched_sets_sample": [],
            "spot_qa_captured_at": "2026-11-05T12:00:00+00:00",
            "board_source": "demo",
            "nightly_slo_ok": True,
            "nightly_elapsed_s": 3600.0,
            "quotes_written": 120,
        },
    )
    client = TestClient(app)
    resp = client.get("/api/data-health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["nightly_slo_ok"] is True
    assert body["nightly_elapsed_s"] == 3600.0
    assert body["quotes_written"] == 120


def test_data_health_spot_fields_expose_slo(monkeypatch) -> None:
    from services import spot_qa

    monkeypatch.setattr(
        spot_qa,
        "compute_live_spot_qa",
        lambda **_k: {
            "cards_total": 1,
            "cards_with_history": 1,
            "history_coverage_pct": 100.0,
            "history_scan": True,
            "quotes_total": 1,
            "sure_rows": 1,
            "board_source": "demo",
        },
    )
    monkeypatch.setattr(
        spot_qa,
        "load_spot_qa_snapshot",
        lambda: {
            "nightly_slo_ok": False,
            "nightly_elapsed_s": 9200.5,
            "quotes_written": 0,
            "captured_at": "2026-11-05T12:00:00+00:00",
        },
    )
    fields = spot_qa.data_health_spot_fields()
    assert fields["nightly_slo_ok"] is False
    assert fields["nightly_elapsed_s"] == 9200.5
    assert fields["quotes_written"] == 0

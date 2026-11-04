"""Soft Ink / API JustTCG data-health counters."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from services import prices as prices_mod


def setup_function() -> None:
    prices_mod.reset_justtcg_observability()


def test_observability_summary_process_counters() -> None:
    prices_mod.record_justtcg_event("live")
    prices_mod.record_justtcg_event("db")
    prices_mod.record_justtcg_event("fallback")
    prices_mod.record_justtcg_event("cache_hit")
    summary = prices_mod.justtcg_observability_summary()
    assert summary["live"] == 1
    assert summary["db"] == 1
    assert summary["fallback"] == 1
    assert summary["cache_hit"] == 1
    assert summary["attempts"] == 3  # live + db + fallback
    assert abs(summary["miss_or_fallback_pct"] - (100.0 / 3.0)) < 1e-6


def test_data_health_endpoint_and_reset() -> None:
    prices_mod.record_justtcg_event("error")
    prices_mod.record_justtcg_event("empty")
    client = TestClient(app)
    resp = client.get("/api/data-health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] >= 1
    assert body["empty"] >= 1
    assert "justtcg_configured" in body
    assert "miss_or_fallback_pct" in body

    reset = client.post("/api/data-health/reset")
    assert reset.status_code == 200
    cleared = reset.json()
    assert cleared["live"] == 0
    assert cleared["db"] == 0
    assert cleared["empty"] == 0
    assert cleared["fallback"] == 0
    assert cleared["error"] == 0
    assert cleared["cache_hit"] == 0
    assert cleared["attempts"] == 0


def test_price_sources_records_db_and_cache(monkeypatch) -> None:
    from api import price_sources_service as pss
    import justtcg_client as jtcg

    pss.clear_price_sources_cache()
    prices_mod.reset_justtcg_observability()

    market = [{"date": f"2024-01-{i:02d}", "price": 10.0 + i} for i in range(1, 12)]
    monkeypatch.setattr(pss, "load_card_history", lambda *_a, **_k: market)
    monkeypatch.setattr(pss, "_resolve_tcp_from_board", lambda _id: ("Card", "Set", "123"))
    monkeypatch.setattr(pss, "justtcg_api_key", lambda: "test-key")
    monkeypatch.setattr(pss, "_market_history_is_fresh", lambda _m: True)
    monkeypatch.setattr(
        jtcg,
        "psa10_history_for_card",
        lambda **_k: ([], "123", {"has_history_series": False}),
    )

    first = pss.build_card_price_sources("sv3-1", limit=90)
    assert first["justtcg_from_db"] is True
    assert first["cache"] == "miss"
    summary = prices_mod.justtcg_observability_summary()
    assert summary["db"] == 1
    assert summary["cache_hit"] == 0

    second = pss.build_card_price_sources("sv3-1", limit=90)
    assert second["cache"] == "hit"
    summary = prices_mod.justtcg_observability_summary()
    assert summary["db"] == 1
    assert summary["cache_hit"] == 1

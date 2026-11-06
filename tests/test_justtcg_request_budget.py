"""JustTCG paid-tier request budget + batch defaults."""

from __future__ import annotations

import pytest

import justtcg_client as jt


@pytest.fixture(autouse=True)
def _reset_budget():
    jt.reset_justtcg_request_count()
    jt.configure_justtcg_request_budget(None)
    jt.clear_justtcg_cache()
    yield
    jt.reset_justtcg_request_count()
    jt.configure_justtcg_request_budget(None)
    jt.clear_justtcg_cache()


def test_request_budget_stops_before_http(monkeypatch):
    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise AssertionError("should not hit network after budget")

    monkeypatch.setattr(jt.requests, "get", boom)
    jt.configure_justtcg_request_budget(2)
    # Seed two successful consumes via _consume_request_budget directly.
    jt._consume_request_budget()
    jt._consume_request_budget()
    assert jt.justtcg_request_count() == 2
    with pytest.raises(jt.JustTCGRateLimitError, match="budget exhausted"):
        jt._get("/sets", {"game": "pokemon"})
    assert calls["n"] == 0


def test_cache_hit_does_not_consume_budget(monkeypatch):
    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"id": "x"}]}

    monkeypatch.setattr(jt, "JUSTTCG_REQUEST_DELAY_SECONDS", 0)
    monkeypatch.setattr(jt, "justtcg_api_key", lambda: "test-key")
    monkeypatch.setattr(jt.requests, "get", lambda *a, **k: _Resp())
    jt.configure_justtcg_request_budget(5)
    first = jt._get("/sets", {"game": "pokemon"})
    second = jt._get("/sets", {"game": "pokemon"})
    assert first == second
    assert jt.justtcg_request_count() == 1


def test_paid_tier_batch_and_delay_defaults():
    import config

    assert int(config.JUSTTCG_BATCH_SIZE) == 100
    assert float(config.JUSTTCG_REQUEST_DELAY_SECONDS) <= 1.25
    assert int(config.JUSTTCG_NIGHTLY_MAX_REQUESTS) == 100
    # 100/night × 30 ≈ 3k; Soft Ink can use ~6k and still stay ≤9k/month.
    assert int(config.JUSTTCG_NIGHTLY_MAX_REQUESTS) * 30 <= 3000


def test_justtcg_max_requests_env(monkeypatch):
    import config

    monkeypatch.setenv("JUSTTCG_MAX_REQUESTS", "150")
    assert config.justtcg_max_requests() == 150
    monkeypatch.setenv("JUSTTCG_MAX_REQUESTS", "off")
    assert config.justtcg_max_requests() is None

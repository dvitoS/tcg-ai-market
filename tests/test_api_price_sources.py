"""Multi-source card price history endpoint (mocked JustTCG — no live key)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app
from api.price_sources_service import clear_price_sources_cache
from justtcg_client import JustTCGRateLimitError


def setup_function() -> None:
    clear_board_cache()
    clear_price_sources_cache()


def _bundle(
    *,
    psa10: tuple | None = None,
    psa9: tuple | None = None,
    tcp: str | None = "tcp-123",
):
    """Build psa_histories_for_card return value."""

    def _inner(**kwargs):
        wanted = [float(g) for g in (kwargs.get("grades") or [10.0])]
        out = {}
        for grade in wanted:
            if grade == 10.0:
                out[10.0] = psa10 or ([], {})
            elif grade == 9.0:
                out[9.0] = psa9 or ([], {})
            else:
                out[grade] = ([], {})
        return out, tcp

    return _inner


def test_card_price_sources_single_flight(monkeypatch) -> None:
    """Concurrent /sources callers share one JustTCG fill."""
    import threading
    import time

    calls = {"n": 0}
    lock = threading.Lock()

    def _slow_nm(**_kwargs):
        with lock:
            calls["n"] += 1
        time.sleep(0.05)
        return ([{"date": "2024-01-01", "price": 9.0}], "tcp-sf")

    monkeypatch.setattr("api.price_sources_service.justtcg_api_key", lambda: "test-key")
    monkeypatch.setattr(
        "api.price_sources_service._market_history_is_fresh",
        lambda _m: False,
    )
    monkeypatch.setattr("justtcg_client.nm_history_for_card", _slow_nm)
    monkeypatch.setattr(
        "justtcg_client.psa_histories_for_card",
        _bundle(tcp="tcp-sf", psa10=([], {"has_history_series": False})),
    )

    from api.price_sources_service import build_card_price_sources, clear_price_sources_cache

    clear_price_sources_cache()
    results: list[dict] = []

    def _run() -> None:
        results.append(build_card_price_sources("sv3-1", limit=60, grades="none"))

    threads = [threading.Thread(target=_run) for _ in range(3)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert len(results) == 3
    assert calls["n"] == 1
    assert all(r["justtcg"] and r["justtcg"][0]["price"] == 9.0 for r in results)
    assert all(r["grades"] == "none" for r in results)


def test_card_price_sources_without_justtcg_key(monkeypatch) -> None:
    monkeypatch.setattr("api.price_sources_service.justtcg_api_key", lambda: "")
    client = TestClient(app)
    listing = client.get("/api/catalog", params={"limit": 1})
    assert listing.status_code == 200
    items = listing.json()["items"]
    if not items:
        return
    card_id = items[0]["id"]
    res = client.get(f"/api/cards/{card_id}/sources")
    assert res.status_code == 200
    body = res.json()
    assert body["card_id"] == card_id
    assert body["justtcg_configured"] is False
    assert isinstance(body["tcgplayer"], list)
    assert body["justtcg"] == []
    assert body["psa10"] == []
    assert body["psa9"] == []
    assert body["grades"] == "none"
    assert body["justtcg_fallback"] is False
    assert "psa10_stats" in body
    assert body["psa10_stats"]["has_history_series"] is False
    assert body["psa9_stats"]["has_history_series"] is False


def test_card_price_sources_default_skips_psa(monkeypatch) -> None:
    """Soft Ink detail default must not burn graded JustTCG quota."""
    calls = {"nm": 0, "psa": 0}

    def _nm(**kwargs):
        calls["nm"] += 1
        return (
            [
                {"date": "2024-01-01", "price": 10.0},
                {"date": "2024-01-02", "price": 11.5},
            ],
            "tcp-123",
        )

    def _histories(**kwargs):
        calls["psa"] += 1
        return _bundle(psa10=([], {"has_history_series": False}))(**kwargs)

    monkeypatch.setattr("api.price_sources_service.justtcg_api_key", lambda: "test-key")
    monkeypatch.setattr(
        "api.price_sources_service._market_history_is_fresh",
        lambda _m: False,
    )
    monkeypatch.setattr("justtcg_client.nm_history_for_card", _nm)
    monkeypatch.setattr("justtcg_client.psa_histories_for_card", _histories)

    client = TestClient(app)
    listing = client.get("/api/catalog", params={"limit": 1})
    assert listing.status_code == 200
    items = listing.json()["items"]
    if not items:
        return
    card_id = items[0]["id"]
    res = client.get(f"/api/cards/{card_id}/sources", params={"limit": 60})
    assert res.status_code == 200
    body = res.json()
    assert body["grades"] == "none"
    assert body["justtcg_configured"] is True
    assert body["tcgplayer_id"] == "tcp-123"
    assert len(body["justtcg"]) == 2
    assert body["psa10"] == []
    assert body["psa9"] == []
    assert calls == {"nm": 1, "psa": 0}


def test_card_price_sources_grades_psa10_only(monkeypatch) -> None:
    calls = {"psa": 0}

    monkeypatch.setattr("api.price_sources_service.justtcg_api_key", lambda: "test-key")
    monkeypatch.setattr(
        "api.price_sources_service._market_history_is_fresh",
        lambda _m: False,
    )
    monkeypatch.setattr(
        "justtcg_client.nm_history_for_card",
        lambda **kwargs: ([{"date": "2024-01-01", "price": 10.0}], "tcp-123"),
    )

    def _histories(**kwargs):
        calls["psa"] += 1
        assert kwargs.get("grades") == [10.0]
        return _bundle(
            psa10=(
                [
                    {"date": "2024-01-01", "price": 40.0},
                    {"date": "2024-01-03", "price": 42.0},
                ],
                {"has_history_series": True, "period_key": "30d", "sales_count": 12},
            )
        )(**kwargs)

    monkeypatch.setattr("justtcg_client.psa_histories_for_card", _histories)

    client = TestClient(app)
    listing = client.get("/api/catalog", params={"limit": 1})
    items = listing.json()["items"]
    if not items:
        return
    card_id = items[0]["id"]
    res = client.get(
        f"/api/cards/{card_id}/sources",
        params={"limit": 60, "grades": "psa10"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["grades"] == "psa10"
    assert len(body["psa10"]) == 2
    assert body["psa10"][1]["price"] == 42.0
    assert body["psa10_stats"]["sales_count"] == 12
    assert body["psa9"] == []
    assert calls == {"psa": 1}


def test_card_price_sources_grades_all(monkeypatch) -> None:
    nm_calls = {"n": 0}

    def _nm(**kwargs):
        nm_calls["n"] += 1
        return ([{"date": "2024-01-01", "price": 99.0}], "tcp-live")

    monkeypatch.setattr(
        "api.price_sources_service.justtcg_api_key",
        lambda: "test-key",
    )
    monkeypatch.setattr("justtcg_client.nm_history_for_card", _nm)
    monkeypatch.setattr(
        "justtcg_client.psa_histories_for_card",
        _bundle(
            psa10=(
                [
                    {"date": "2024-01-01", "price": 40.0},
                    {"date": "2024-01-03", "price": 42.0},
                ],
                {
                    "has_history_series": True,
                    "period_key": "30d",
                    "sales_count": 12,
                },
            ),
            psa9=(
                [{"date": "2024-01-03", "price": 28.0}],
                {
                    "has_history_series": False,
                    "period_key": "30d",
                    "sales_count": 7,
                },
            ),
        ),
    )
    monkeypatch.setattr(
        "api.price_sources_service.load_card_history",
        lambda card_id, limit=180: [
            {"date": "2024-01-01", "price": 10.0},
            {"date": "2024-01-02", "price": 11.5},
        ],
    )
    client = TestClient(app)
    res = client.get(
        "/api/cards/grades-all-card/sources",
        params={"limit": 60, "grades": "all"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["grades"] == "all"
    assert body["justtcg_configured"] is True
    assert body["tcgplayer_id"] == "tcp-123"
    # Graded mode reuses market NM — no second live NM burn.
    assert nm_calls["n"] == 0
    assert len(body["justtcg"]) == 2
    assert body["justtcg"][0]["price"] == 10.0
    assert body["justtcg_from_db"] is True
    assert len(body["psa10"]) == 2
    assert body["psa10"][1]["price"] == 42.0
    assert body["psa10_stats"]["has_history_series"] is True
    assert body["psa10_stats"]["sales_count"] == 12
    assert body["psa9"][0]["price"] == 28.0
    assert body["psa9_stats"]["sales_count"] == 7
    assert body["justtcg_error"] is None
    assert body["psa10_error"] is None
    assert body["psa9_error"] is None


def test_card_price_sources_justtcg_fallback_to_market(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.price_sources_service.justtcg_api_key",
        lambda: "test-key",
    )
    monkeypatch.setattr(
        "justtcg_client.nm_history_for_card",
        lambda **kwargs: ([], None),
    )
    monkeypatch.setattr(
        "justtcg_client.psa_histories_for_card",
        _bundle(
            tcp=None,
            psa10=([], {"has_history_series": False, "sales_count": 0}),
        ),
    )
    monkeypatch.setattr(
        "api.price_sources_service.load_card_history",
        lambda card_id, limit=180: [
            {"date": "2024-02-01", "price": 3.25},
            {"date": "2024-02-02", "price": 3.4},
        ],
    )
    client = TestClient(app)
    res = client.get("/api/cards/demo-card/sources")
    assert res.status_code == 200
    body = res.json()
    assert body["justtcg_fallback"] is True
    assert len(body["justtcg"]) == 2
    assert body["justtcg"][0]["price"] == 3.25
    assert body["psa10"] == []
    assert body["grades"] == "none"


def test_card_price_sources_caches_live_justtcg(monkeypatch) -> None:
    """Second Soft Ink detail view must not re-call JustTCG within the TTL."""
    calls = {"nm": 0, "psa": 0}

    def _nm(**kwargs):
        calls["nm"] += 1
        return ([{"date": "2024-01-01", "price": 9.0}], "tcp-1")

    def _histories(**kwargs):
        calls["psa"] += 1
        return _bundle(
            tcp="tcp-1",
            psa10=([], {"has_history_series": False, "sales_count": 0}),
        )(**kwargs)

    monkeypatch.setattr("api.price_sources_service.justtcg_api_key", lambda: "test-key")
    monkeypatch.setattr("justtcg_client.nm_history_for_card", _nm)
    monkeypatch.setattr("justtcg_client.psa_histories_for_card", _histories)
    monkeypatch.setattr(
        "api.price_sources_service.load_card_history",
        lambda card_id, limit=180: [{"date": "2024-01-01", "price": 8.0}],
    )

    client = TestClient(app)
    first = client.get("/api/cards/cache-card/sources")
    second = client.get("/api/cards/cache-card/sources")
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["cache"] == "miss"
    assert second.json()["cache"] == "hit"
    # Default grades=none — NM once, no graded burn on cache warm.
    assert calls == {"nm": 1, "psa": 0}
    assert second.json()["justtcg"][0]["price"] == 9.0

    graded = client.get("/api/cards/cache-card/sources", params={"grades": "psa10"})
    assert graded.status_code == 200
    assert graded.json()["grades"] == "psa10"
    # Graded follow-up reuses DB/market NM — one multi-grade JustTCG call.
    assert calls == {"nm": 1, "psa": 1}


def test_card_price_sources_uses_fresh_db_nm_without_live_call(monkeypatch) -> None:
    """Fresh nightly price_history should skip live JustTCG NM (quota)."""
    from datetime import date, timedelta

    calls = {"nm": 0, "psa": 0}
    today = date.today()
    market = [
        {"date": (today - timedelta(days=i)).isoformat(), "price": 10.0 + i}
        for i in range(14, -1, -1)
    ]

    def _nm(**kwargs):
        calls["nm"] += 1
        return ([{"date": today.isoformat(), "price": 99.0}], "tcp-db")

    def _histories(**kwargs):
        calls["psa"] += 1
        assert kwargs.get("grades") == [10.0, 9.0]
        return _bundle(
            tcp="tcp-db",
            psa10=(
                [{"date": today.isoformat(), "price": 50.0}],
                {"has_history_series": True, "period_key": "30d", "sales_count": 3},
            ),
            psa9=(
                [{"date": today.isoformat(), "price": 32.0}],
                {"has_history_series": False, "period_key": "30d", "sales_count": 5},
            ),
        )(**kwargs)

    monkeypatch.setattr("api.price_sources_service.justtcg_api_key", lambda: "test-key")
    monkeypatch.setattr("justtcg_client.nm_history_for_card", _nm)
    monkeypatch.setattr("justtcg_client.psa_histories_for_card", _histories)
    monkeypatch.setattr(
        "api.price_sources_service.load_card_history",
        lambda card_id, limit=180: market,
    )

    client = TestClient(app)
    res = client.get("/api/cards/fresh-db-card/sources")
    assert res.status_code == 200
    body = res.json()
    assert calls["nm"] == 0
    assert calls["psa"] == 0
    assert body["justtcg_from_db"] is True
    assert body["justtcg_fallback"] is False
    assert body["grades"] == "none"
    assert len(body["justtcg"]) == 15
    assert body["justtcg"][-1]["price"] == market[-1]["price"]
    assert body["psa10"] == []
    assert body["psa9"] == []

    graded = client.get(
        "/api/cards/fresh-db-card/sources",
        params={"grades": "all"},
    )
    assert graded.status_code == 200
    gbody = graded.json()
    assert calls["nm"] == 0
    assert calls["psa"] == 1  # one JustTCG call for PSA 9+10
    assert gbody["grades"] == "all"
    assert len(gbody["psa10"]) == 1
    assert len(gbody["psa9"]) == 1


def test_card_price_sources_skips_psa10_after_nm_rate_limit(monkeypatch) -> None:
    calls = {"psa": 0}

    def _nm(**kwargs):
        raise JustTCGRateLimitError(response=None)

    def _histories(**kwargs):
        calls["psa"] += 1
        return _bundle(tcp=None)(**kwargs)

    monkeypatch.setattr("api.price_sources_service.justtcg_api_key", lambda: "test-key")
    monkeypatch.setattr("justtcg_client.nm_history_for_card", _nm)
    monkeypatch.setattr("justtcg_client.psa_histories_for_card", _histories)
    monkeypatch.setattr(
        "api.price_sources_service.load_card_history",
        lambda card_id, limit=180: [{"date": "2024-01-01", "price": 1.0}],
    )

    client = TestClient(app)
    # grades=none takes the live NM path; 429 there must block graded follow-ups.
    res = client.get("/api/cards/rl-card/sources")
    assert res.status_code == 200
    body = res.json()
    assert calls["psa"] == 0
    assert "rate limited" in (body["justtcg_error"] or "").lower()
    assert body["justtcg_fallback"] is True
    assert body["cache"] == "miss"
    # Rate-limited responses must not populate the TTL cache.
    again = client.get("/api/cards/rl-card/sources")
    assert again.json()["cache"] == "miss"

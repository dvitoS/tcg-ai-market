"""USD→EUR FX endpoint for Soft Ink dual-currency spots."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.fx_service import clear_fx_cache
from api.main import app


def setup_function() -> None:
    clear_fx_cache()


def test_fx_quote_live_frankfurter(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.fx_service._fetch_frankfurter",
        lambda: {
            "usd_eur": 0.91,
            "as_of": "2026-11-06",
            "source": "frankfurter",
            "fallback": False,
        },
    )
    client = TestClient(app)
    res = client.get("/api/fx")
    assert res.status_code == 200
    body = res.json()
    assert body["usd_eur"] == 0.91
    assert body["source"] == "frankfurter"
    assert body["fallback"] is False
    assert body["as_of"] == "2026-11-06"

    # Cached — second call must not re-fetch if we break the fetcher.
    monkeypatch.setattr(
        "api.fx_service._fetch_frankfurter",
        lambda: (_ for _ in ()).throw(RuntimeError("nope")),
    )
    again = client.get("/api/fx")
    assert again.json()["usd_eur"] == 0.91


def test_fx_quote_fallback_on_error(monkeypatch) -> None:
    def _boom():
        raise TimeoutError("down")

    monkeypatch.setattr("api.fx_service._fetch_frankfurter", _boom)
    client = TestClient(app)
    res = client.get("/api/fx")
    assert res.status_code == 200
    body = res.json()
    assert body["fallback"] is True
    assert body["source"] == "fallback"
    assert body["usd_eur"] > 0

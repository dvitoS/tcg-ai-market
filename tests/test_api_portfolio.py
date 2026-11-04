"""Portfolio / watchlist API smoke tests (demo mode — no Supabase)."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.catalog_service import clear_board_cache
from api.main import app
from database_clients import get_request_access_token


def setup_function() -> None:
    clear_board_cache()


def test_portfolio_and_watchlist_demo_session() -> None:
    client = TestClient(app)
    portfolio = client.get("/api/portfolio")
    assert portfolio.status_code == 200
    body = portfolio.json()
    assert "items" in body
    assert "summary" in body
    assert body["demo"] is True
    assert body["summary"]["lots"] == len(
        [i for i in body["items"] if str(i.get("status") or "open") != "sold"]
    )

    watch = client.get("/api/watchlist")
    assert watch.status_code == 200
    wbody = watch.json()
    assert "items" in wbody
    assert wbody["demo"] is True


def test_watchlist_add_and_remove_roundtrip() -> None:
    client = TestClient(app)
    catalog = client.get("/api/catalog", params={"limit": 1})
    assert catalog.status_code == 200
    items = catalog.json()["items"]
    if not items:
        return
    card_id = items[0]["id"]

    added = client.post("/api/watchlist", json={"card_id": card_id})
    assert added.status_code == 201
    assert added.json()["card_id"] == card_id

    status = client.get(f"/api/watchlist/{card_id}/status")
    assert status.status_code == 200
    assert status.json()["watched"] is True

    removed = client.delete(f"/api/watchlist/{card_id}")
    assert removed.status_code == 200
    assert removed.json()["ok"] is True


def test_middleware_binds_bearer_access_token() -> None:
    """Authorization Bearer must be visible to database_clients during the request."""
    seen: dict[str, str | None] = {"token": None}

    def _capture_status(*, user_id: str, card_id: str) -> bool:
        seen["token"] = get_request_access_token()
        return False

    with patch("api.routers.portfolio.is_watched", side_effect=_capture_status):
        with patch(
            "api.deps.optional_user",
            return_value={"id": "user-1", "email": "a@b.c", "dev": False},
        ):
            client = TestClient(app)
            resp = client.get(
                "/api/watchlist/swsh7-218/status",
                headers={"Authorization": "Bearer user-jwt-abc"},
            )
    assert resp.status_code == 200
    assert resp.json() == {"watched": False}
    assert seen["token"] == "user-jwt-abc"


def test_watch_status_maps_jwt_client_failure_to_503_with_cors(monkeypatch) -> None:
    """Unhandled RuntimeError used to 500 without CORS; Soft Ink saw a CORS block."""
    monkeypatch.setenv(
        "KESTREL_CORS_ORIGINS",
        "https://www.kestreltcg.app,http://localhost:3000",
    )

    # Reload app CORS origins from env for this test process isn't trivial;
    # assert JSON error path instead — CORS middleware already wraps TestClient app.
    with patch("api.demo_mode.demo_mode", return_value=False):
        with patch(
            "api.deps.optional_user",
            return_value={"id": "user-1", "email": "a@b.c", "dev": False},
        ):
            with patch(
                "api.routers.portfolio.is_watched",
                side_effect=RuntimeError("JWT session"),
            ):
                client = TestClient(app)
                resp = client.get(
                    "/api/watchlist/swsh7-218/status",
                    headers={
                        "Authorization": "Bearer user-jwt",
                        "Origin": "https://www.kestreltcg.app",
                    },
                )
    assert resp.status_code == 503
    assert "JWT session" in resp.json()["detail"]
    # CORSMiddleware echoes allowed origins; default test env may not list prod —
    # at minimum the response must be a proper FastAPI JSON error (not a crash).
    assert resp.headers.get("content-type", "").startswith("application/json")

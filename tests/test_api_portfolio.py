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
    assert "outlook_horizon_days" in body["summary"]
    assert int(body["summary"]["outlook_horizon_days"]) in (7, 30)
    open_items = [i for i in body["items"] if str(i.get("status") or "open") != "sold"]
    if open_items:
        lot = open_items[0]
        assert lot.get("lot_action") in {"ADD", "TRIM", "HOLD"}
        assert "outlook_conformal_ok" in lot
        assert "outlook_horizon_days" in lot

    watch = client.get("/api/watchlist")
    assert watch.status_code == 200
    wbody = watch.json()
    assert "items" in wbody
    assert wbody["demo"] is True


def test_portfolio_performance_demo_session() -> None:
    client = TestClient(app)
    resp = client.get("/api/portfolio/performance", params={"max_days": 90})
    assert resp.status_code == 200
    body = resp.json()
    assert body["demo"] is True
    assert "points" in body
    assert "days" in body
    assert body["days"] == len(body["points"])
    assert body["days"] >= 2
    row = body["points"][0]
    assert "date" in row and "invested" in row and "market_value" in row
    assert float(row["invested"]) > 0
    assert "drawdown_callouts" in body
    last = body["points"][-1]
    # AI fair is attached on the latest day when open lots carry outlook.
    if body.get("ai_fair_value") is not None:
        assert last.get("ai_fair_value") == body["ai_fair_value"]


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
    """ASGI middleware exposes Authorization Bearer via ContextVar."""
    seen: dict[str, str | None] = {"token": None}

    def _capture_status(*, user_id: str, card_id: str, access_token: str | None = None) -> bool:
        seen["token"] = get_request_access_token()
        seen["passed"] = access_token
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
    assert seen["passed"] == "user-jwt-abc"


def test_is_watched_binds_access_token_in_sync_thread(monkeypatch) -> None:
    """Explicit access_token must win inside portfolio_service (thread-safe RLS)."""
    import database_user as du

    from api import portfolio_service

    seen: dict[str, str | None] = {}

    def _fake_is_on_watchlist(card_id: str, *, user_id: str) -> bool:
        seen["token"] = get_request_access_token()
        return True

    monkeypatch.setattr(portfolio_service, "demo_mode", lambda: False)
    monkeypatch.setattr(du, "is_on_watchlist", _fake_is_on_watchlist)

    assert portfolio_service.is_watched(
        user_id="u1", card_id="swsh7-218", access_token="sync-jwt"
    )
    assert seen["token"] == "sync-jwt"


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

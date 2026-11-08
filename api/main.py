"""Kestrel FastAPI entrypoint.

Run from repo root:
  PYTHONPATH=. uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.bearer_middleware import BindBearerAccessTokenMiddleware
from api.routers import (
    auth,
    billing,
    binder,
    cards,
    catalog,
    dealer,
    funnel,
    fx,
    health,
    identify,
    market,
    portfolio,
    radar,
    scanner,
    sealed,
    trade,
    trust,
    webhooks,
)

LOG = logging.getLogger("kestrel.api")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Warm market_quotes into memory so cold Radar is usable after deploy."""
    try:
        from api.catalog_service import load_board

        board, source = load_board()
        LOG.info(
            "Board warm complete: source=%s rows=%s",
            source,
            0 if board is None else len(board),
        )
    except Exception as exc:
        LOG.warning("Board warm skipped: %s", exc)
    yield


app = FastAPI(
    title="Kestrel API",
    version="0.1.0",
    description="HTTP API for Soft Ink (Next.js) — the primary Kestrel UI. Streamlit is legacy.",
    lifespan=lifespan,
)

_origins = [
    o.strip()
    for o in os.getenv(
        "KESTREL_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if o.strip()
]
# Soft Ink local / PWA demos often use non-3000 ports (camera OCR, next start).
for _port in (3000, 3001, 3456, 3457, 3458, 4173):
    for _host in ("http://localhost", "http://127.0.0.1"):
        _origin = f"{_host}:{_port}"
        if _origin not in _origins:
            _origins.append(_origin)

# Pure ASGI bearer bind (inner); CORS last so it stays outermost on error responses.
app.add_middleware(BindBearerAccessTokenMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(fx.router, prefix="/api")
app.include_router(billing.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(cards.router, prefix="/api")
app.include_router(identify.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(binder.router, prefix="/api")
app.include_router(scanner.router, prefix="/api")
app.include_router(radar.router, prefix="/api")
app.include_router(trust.router, prefix="/api")
app.include_router(sealed.router, prefix="/api")
app.include_router(trade.router, prefix="/api")
app.include_router(dealer.router, prefix="/api")
app.include_router(funnel.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "kestrel-api", "docs": "/docs", "health": "/api/health"}

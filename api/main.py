"""Kestrel FastAPI entrypoint.

Run from repo root:
  PYTHONPATH=. uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.bearer_middleware import BindBearerAccessTokenMiddleware
from api.routers import auth, billing, cards, catalog, dealer, health, portfolio, radar, scanner, trade, webhooks

LOG = logging.getLogger("kestrel.api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Kestrel API",
    version="0.1.0",
    description="HTTP API for Soft Ink (Next.js) — the primary Kestrel UI. Streamlit is legacy.",
)

_origins = [
    o.strip()
    for o in os.getenv(
        "KESTREL_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if o.strip()
]

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
app.include_router(billing.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(cards.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(scanner.router, prefix="/api")
app.include_router(radar.router, prefix="/api")
app.include_router(trade.router, prefix="/api")
app.include_router(dealer.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "kestrel-api", "docs": "/docs", "health": "/api/health"}

"""Kestrel FastAPI entrypoint.

Run from repo root:
  PYTHONPATH=. uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from api.routers import auth, billing, cards, catalog, dealer, health, portfolio, scanner, webhooks
from database_clients import reset_request_access_token, set_request_access_token

LOG = logging.getLogger("kestrel.api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Kestrel API",
    version="0.1.0",
    description="HTTP surface for the Next.js Kestrel frontend. Streamlit remains until cutover.",
)

_origins = [
    o.strip()
    for o in os.getenv(
        "KESTREL_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if o.strip()
]


class BindBearerAccessTokenMiddleware(BaseHTTPMiddleware):
    """Expose Authorization Bearer to database_user via ContextVar (RLS JWT)."""

    async def dispatch(self, request: Request, call_next):
        authorization = request.headers.get("authorization") or ""
        scheme, _, token = authorization.partition(" ")
        raw = token.strip() if scheme.lower() == "bearer" else ""
        ctx = set_request_access_token(raw or None)
        try:
            return await call_next(request)
        finally:
            reset_request_access_token(ctx)


# Bind Bearer first (inner); CORS last so it stays outermost and covers error responses.
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
app.include_router(dealer.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "kestrel-api", "docs": "/docs", "health": "/api/health"}

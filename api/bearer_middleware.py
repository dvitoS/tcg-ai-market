"""Pure ASGI middleware — binds Authorization Bearer into a ContextVar.

Starlette ``BaseHTTPMiddleware`` runs the app in a child task and drops
ContextVars, so portfolio/watchlist RLS never saw the Soft Ink JWT in prod.
"""

from __future__ import annotations

from typing import Callable

from database_clients import reset_request_access_token, set_request_access_token


class BindBearerAccessTokenMiddleware:
    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        authorization = ""
        for key, value in scope.get("headers") or []:
            if key == b"authorization":
                authorization = value.decode("latin-1")
                break

        scheme, _, token = authorization.partition(" ")
        raw = token.strip() if scheme.lower() == "bearer" else ""
        ctx = set_request_access_token(raw or None)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_request_access_token(ctx)

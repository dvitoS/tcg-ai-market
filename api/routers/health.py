"""Health / readiness."""

from __future__ import annotations

import os

from fastapi import APIRouter

from api.catalog_service import load_board
from api.schemas import HealthResponse
from services.creem_webhooks import creem_webhook_secret
from services.pro import pro_checkout_url, pro_open_beta

router = APIRouter(tags=["health"])


def _deploy_git_sha() -> str | None:
    raw = (
        os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("KESTREL_GIT_SHA")
        or os.getenv("GITHUB_SHA")
        or ""
    ).strip()
    return raw or None


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    _, source = load_board()
    return HealthResponse(
        status="ok",
        source=source,
        creem_webhook_secret=bool(creem_webhook_secret()),
        pro_checkout_url=bool(pro_checkout_url()),
        pro_open=bool(pro_open_beta()),
        git_sha=_deploy_git_sha(),
    )

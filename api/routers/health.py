"""Health / readiness."""

from __future__ import annotations

from fastapi import APIRouter

from api.catalog_service import load_board
from api.schemas import HealthResponse
from services.creem_webhooks import creem_webhook_secret
from services.pro import pro_checkout_url, pro_open_beta

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    _, source = load_board()
    return HealthResponse(
        status="ok",
        source=source,
        creem_webhook_secret=bool(creem_webhook_secret()),
        pro_checkout_url=bool(pro_checkout_url()),
        pro_open=bool(pro_open_beta()),
    )

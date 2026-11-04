"""Health / readiness + Soft Ink data-health counters."""

from __future__ import annotations

import os

from fastapi import APIRouter

from api.catalog_service import load_board
from api.price_sources_service import clear_price_sources_cache
from api.schemas import DataHealthResponse, HealthResponse
from justtcg_client import justtcg_api_key
from services.creem_webhooks import creem_webhook_secret
from services.prices import (
    justtcg_observability_summary,
    reset_justtcg_observability,
)
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


@router.get("/data-health", response_model=DataHealthResponse)
def data_health() -> DataHealthResponse:
    summary = justtcg_observability_summary()
    return DataHealthResponse(
        live=int(summary.get("live") or 0),
        db=int(summary.get("db") or 0),
        empty=int(summary.get("empty") or 0),
        fallback=int(summary.get("fallback") or 0),
        error=int(summary.get("error") or 0),
        cache_hit=int(summary.get("cache_hit") or 0),
        attempts=int(summary.get("attempts") or 0),
        miss_or_fallback_pct=float(summary.get("miss_or_fallback_pct") or 0.0),
        justtcg_configured=bool(justtcg_api_key()),
    )


@router.post("/data-health/reset", response_model=DataHealthResponse)
def data_health_reset() -> DataHealthResponse:
    """Clear Soft Ink price-source TTL cache + zero process JustTCG counters."""
    clear_price_sources_cache()
    reset_justtcg_observability()
    return data_health()

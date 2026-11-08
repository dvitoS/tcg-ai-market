"""Health / readiness + Soft Ink data-health counters."""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from api.catalog_service import load_board
from api.deps import require_ops_user
from api.price_sources_service import clear_price_sources_cache
from api.schemas import (
    DataHealthResponse,
    HealthResponse,
    SpotHealRequest,
    SpotHealResponse,
    SpotSniffPackResponse,
)
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
def data_health(
    _ops: Annotated[dict[str, Any], Depends(require_ops_user)],
) -> DataHealthResponse:
    summary = justtcg_observability_summary()
    try:
        from services.spot_qa import data_health_spot_fields

        spot = data_health_spot_fields()
    except Exception:
        spot = {}
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
        cards_total=int(spot.get("cards_total") or 0),
        cards_with_history=int(spot.get("cards_with_history") or 0),
        history_coverage_pct=float(spot.get("history_coverage_pct") or 0.0),
        fresh_history_pct=(
            float(spot["fresh_history_pct"])
            if spot.get("fresh_history_pct") is not None
            else None
        ),
        sure_rows=int(spot.get("sure_rows") or 0),
        quotes_total=int(spot.get("quotes_total") or 0),
        spot_quarantine_rows=int(spot.get("spot_quarantine_rows") or 0),
        spot_poison_clusters=int(spot.get("spot_poison_clusters") or 0),
        spot_poison_cluster_sample=list(spot.get("spot_poison_cluster_sample") or [])[:6],
        unmatched_sets_count=(
            int(spot["unmatched_sets_count"])
            if spot.get("unmatched_sets_count") is not None
            else None
        ),
        unmatched_sets_sample=list(spot.get("unmatched_sets_sample") or []),
        spot_qa_captured_at=spot.get("spot_qa_captured_at"),
        board_source=str(spot.get("board_source") or "empty"),
        nightly_slo_ok=(
            bool(spot["nightly_slo_ok"])
            if spot.get("nightly_slo_ok") is not None
            else None
        ),
        nightly_elapsed_s=(
            float(spot["nightly_elapsed_s"])
            if spot.get("nightly_elapsed_s") is not None
            else None
        ),
        quotes_written=(
            int(spot["quotes_written"])
            if spot.get("quotes_written") is not None
            else None
        ),
    )


@router.post("/data-health/reset", response_model=DataHealthResponse)
def data_health_reset(
    ops: Annotated[dict[str, Any], Depends(require_ops_user)],
) -> DataHealthResponse:
    """Clear board + Soft Ink TTL caches and zero process JustTCG counters."""
    from api.catalog_service import clear_board_cache

    clear_board_cache()
    clear_price_sources_cache()
    reset_justtcg_observability()
    return data_health(ops)


@router.get("/data-health/sniff-pack", response_model=SpotSniffPackResponse)
def data_health_sniff_pack(
    _ops: Annotated[dict[str, Any], Depends(require_ops_user)],
    limit: int = 20,
) -> SpotSniffPackResponse:
    """Ops M0.2: sample sure UNDER/OVER rows for manual TCP + eBay sniff."""
    from api.catalog_service import clear_board_cache
    from services.spot_sniff import build_spot_sniff_pack

    # Bust process cache; load_board revision check + radar load the board once.
    clear_board_cache()
    payload = build_spot_sniff_pack(limit=limit)
    return SpotSniffPackResponse(**payload)


def _spot_heal_response(result: dict, *, mode: str) -> SpotHealResponse:
    return SpotHealResponse(
        mode=str(result.get("mode") or mode),
        count=int(result.get("count") or 0),
        ids=list(result.get("ids") or [])[:50],
        poison_keys=[float(x) for x in list(result.get("poison_keys") or [])],
        nulled=int(result.get("nulled") or 0),
        history_cleared=int(result.get("history_cleared") or 0),
        quotes_quarantined=int(result.get("quotes_quarantined") or 0),
        updated=int(result.get("updated") or 0),
        skipped=int(result.get("skipped") or 0),
        skip_poison=int(result.get("skip_poison") or 0),
        skip_absurd=int(result.get("skip_absurd") or 0),
        saved=int(result.get("saved") or 0),
    )


@router.post("/data-health/heal-spots", response_model=SpotHealResponse)
def data_health_heal_spots(
    body: SpotHealRequest,
    _ops: Annotated[dict[str, Any], Depends(require_ops_user)],
) -> SpotHealResponse:
    """Ops: detect / soft-clear / refetch poisoned identical JustTCG spots."""
    from api.catalog_service import clear_board_cache
    from services.spot_heal import heal_poisoned_spots

    ids = None
    if body.card_ids:
        ids = [str(cid).strip() for cid in body.card_ids if str(cid).strip()][:100]
    result = heal_poisoned_spots(mode=body.mode, limit=body.limit, card_ids=ids)
    if body.mode != "dry_run":
        clear_board_cache()
        clear_price_sources_cache()
    return _spot_heal_response(result, mode=body.mode)


@router.post("/data-health/heal-auto-unsafe", response_model=SpotHealResponse)
def data_health_heal_auto_unsafe(
    body: SpotHealRequest,
    _ops: Annotated[dict[str, Any], Depends(require_ops_user)],
) -> SpotHealResponse:
    """Ops: one-shot quarantine Energy / rarity-cap / cluster tips (no sniff clicks)."""
    from api.catalog_service import clear_board_cache
    from services.spot_heal import heal_auto_unsafe_spots

    mode = body.mode if body.mode != "dry_run" else "null_market"
    if body.mode == "dry_run":
        mode = "dry_run"
    result = heal_auto_unsafe_spots(mode=mode, limit=body.limit or 200)
    if mode != "dry_run":
        clear_board_cache()
        clear_price_sources_cache()
    return _spot_heal_response(result, mode=mode)

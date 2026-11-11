"""Sealed product quotes for Soft Ink portfolio (ETB / box / tin)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import optional_user, require_user
from api.schemas import (
    CatalogCard,
    SealedDetailResponse,
    SealedDetailSummary,
    SealedEnsureRequest,
    SealedQuoteItem,
    SealedQuoteResponse,
    SealedRarityGroup,
)
from api.sealed_service import ensure_sealed_card, quote_sealed_products, sealed_product_detail

router = APIRouter(prefix="/sealed", tags=["sealed"])


@router.get("/quote", response_model=SealedQuoteResponse)
def sealed_quote(
    user: Annotated[dict | None, Depends(optional_user)] = None,
    q: str | None = Query(default=None, max_length=120),
    tcgplayer_id: str | None = Query(default=None, max_length=64),
    gtin: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=8, ge=1, le=48),
) -> SealedQuoteResponse:
    """Public Soft Ink sealed desk — search or empty showcase (demo seed).

    Adding lots still requires auth via ``/ensure`` + portfolio.
    """
    del user
    payload = quote_sealed_products(
        q=q,
        tcgplayer_id=tcgplayer_id,
        gtin=gtin,
        limit=limit,
        allow_showcase=not (q or tcgplayer_id or gtin),
    )
    return SealedQuoteResponse(
        items=[SealedQuoteItem(**item) for item in payload.get("items") or []],
        source=payload.get("source") or "empty",
        justtcg_configured=bool(payload.get("justtcg_configured")),
        error=payload.get("error"),
    )


@router.get("/{tcgplayer_id}", response_model=SealedDetailResponse)
def sealed_detail(
    tcgplayer_id: str,
    user: Annotated[dict | None, Depends(optional_user)] = None,
    hits_limit: int = Query(default=48, ge=1, le=72),
) -> SealedDetailResponse:
    """Sealed product detail — price + set chase singles (box vs hits)."""
    del user
    payload = sealed_product_detail(tcgplayer_id, hits_limit=hits_limit)
    if not payload or not payload.get("product"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sealed product not found.",
        )
    summary_raw = payload.get("summary")
    return SealedDetailResponse(
        product=SealedQuoteItem(**payload["product"]),
        shelf=[SealedQuoteItem(**row) for row in payload.get("shelf") or []],
        hits=[CatalogCard(**row) for row in payload.get("hits") or []],
        groups=[SealedRarityGroup(**row) for row in payload.get("groups") or []],
        summary=SealedDetailSummary(**summary_raw) if summary_raw else None,
        source=payload.get("source") or "empty",
        justtcg_configured=bool(payload.get("justtcg_configured")),
        set_name=payload.get("set_name"),
    )


@router.post("/ensure", response_model=SealedQuoteItem)
def sealed_ensure(
    body: SealedEnsureRequest,
    user: Annotated[dict, Depends(require_user)],
) -> SealedQuoteItem:
    del user
    hit = {
        "card_id": body.card_id
        or (f"sealed:{body.tcgplayer_id}" if body.tcgplayer_id else ""),
        "name": body.name,
        "set_name": body.set_name,
        "tcgplayer_id": body.tcgplayer_id,
        "gtin": body.gtin,
        "spot_usd": body.spot_usd,
        "image_url": body.image_url,
        "source": body.source or "justtcg",
        "kind": "sealed",
    }
    if not str(hit["card_id"]).startswith("sealed:"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sealed ensure requires a sealed:* card_id or tcgplayer_id.",
        )
    try:
        ensured = ensure_sealed_card(hit)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not ensure sealed card: {exc}",
        ) from exc
    return SealedQuoteItem(**ensured)

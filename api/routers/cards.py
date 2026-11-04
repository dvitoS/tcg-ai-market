"""Card detail + price history + eBay comps."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from api.catalog_service import history_stats, load_board, load_card_history, row_to_card
from api.schemas import (
    CardDetailResponse,
    CardHistoryResponse,
    CatalogCard,
    EbayCompsResponse,
    EbayListing,
    EbaySoldStats,
    HistoryPoint,
    HistoryStats,
)
from services.ebay_listings import build_ebay_detail_payload

router = APIRouter(prefix="/cards", tags=["cards"])


def _pred_band(row) -> tuple[float | None, float | None]:
    pred_lo = row.get("pred_lo_pct")
    pred_hi = row.get("pred_hi_pct")
    try:
        pred_lo_f = float(pred_lo) if pred_lo is not None else None
    except (TypeError, ValueError):
        pred_lo_f = None
    try:
        pred_hi_f = float(pred_hi) if pred_hi is not None else None
    except (TypeError, ValueError):
        pred_hi_f = None
    return pred_lo_f, pred_hi_f


@router.get("/{card_id}", response_model=CardDetailResponse)
def card_detail(card_id: str) -> CardDetailResponse:
    board, source = load_board()
    if board is None or board.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
    hits = board[board["id"].astype(str) == str(card_id)]
    if hits.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
    row = hits.iloc[0]
    card = CatalogCard(**row_to_card(row))
    pred_lo_f, pred_hi_f = _pred_band(row)
    points = load_card_history(card_id, limit=180)
    return CardDetailResponse(
        card=card,
        pred_lo_pct=pred_lo_f,
        pred_hi_pct=pred_hi_f,
        history=HistoryStats(**history_stats(points)),
        source=source,
    )


@router.get("/{card_id}/history", response_model=CardHistoryResponse)
def card_history(
    card_id: str,
    limit: int = Query(default=180, ge=7, le=730),
) -> CardHistoryResponse:
    raw = load_card_history(card_id, limit=limit)
    points = [HistoryPoint(**p) for p in raw]
    return CardHistoryResponse(
        card_id=str(card_id),
        points=points,
        stats=HistoryStats(**history_stats(raw)),
    )


@router.get("/{card_id}/ebay", response_model=EbayCompsResponse)
def card_ebay_comps(
    card_id: str,
    limit: int = Query(default=8, ge=1, le=20),
) -> EbayCompsResponse:
    board, _source = load_board()
    name = str(card_id)
    set_name = ""
    if board is not None and not board.empty:
        hits = board[board["id"].astype(str) == str(card_id)]
        if not hits.empty:
            row = hits.iloc[0]
            name = str(row.get("name") or card_id)
            set_name = str(row.get("set_name") or "")

    payload = build_ebay_detail_payload(
        card_id=str(card_id),
        name=name,
        set_name=set_name,
        limit=limit,
    )
    return EbayCompsResponse(
        card_id=str(card_id),
        configured=bool(payload.get("configured")),
        epn=bool(payload.get("epn")),
        listings=[EbayListing(**r) for r in (payload.get("listings") or []) if isinstance(r, dict)],
        listings_error=payload.get("listings_error"),
        sold=[EbayListing(**r) for r in (payload.get("sold") or []) if isinstance(r, dict)],
        sold_hint=payload.get("sold_hint"),
        sold_stats=EbaySoldStats(**(payload.get("sold_stats") or {})),
        sold_fallback_active=bool(payload.get("sold_fallback_active")),
        active_fallback=[
            EbayListing(**r) for r in (payload.get("active_fallback") or []) if isinstance(r, dict)
        ],
    )

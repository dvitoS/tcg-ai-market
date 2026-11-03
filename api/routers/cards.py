"""Card detail + price history."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from api.catalog_service import load_board, load_card_history, row_to_card
from api.schemas import CardDetailResponse, CardHistoryResponse, CatalogCard, HistoryPoint

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/{card_id}", response_model=CardDetailResponse)
def card_detail(card_id: str) -> CardDetailResponse:
    board, _source = load_board()
    if board is None or board.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
    hits = board[board["id"].astype(str) == str(card_id)]
    if hits.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
    row = hits.iloc[0]
    card = CatalogCard(**row_to_card(row))
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
    return CardDetailResponse(card=card, pred_lo_pct=pred_lo_f, pred_hi_pct=pred_hi_f)


@router.get("/{card_id}/history", response_model=CardHistoryResponse)
def card_history(
    card_id: str,
    limit: int = Query(default=180, ge=7, le=730),
) -> CardHistoryResponse:
    points = [HistoryPoint(**p) for p in load_card_history(card_id, limit=limit)]
    return CardHistoryResponse(card_id=str(card_id), points=points)

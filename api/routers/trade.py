"""Trade Analyzer — Soft Pro two-sided deal desk."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from api.catalog_service import load_board
from api.demo_mode import demo_mode
from api.deps import require_user
from api.schemas import TradeRequest, TradeResponse, TradeStatus
from api.trade_service import FAIR_SPOT_BAND_PCT, analyze_trade
from services.pro import is_pro_user, pro_checkout_url, pro_gate_reason

router = APIRouter(prefix="/trade", tags=["trade"])


def _pro_allowed(user: dict[str, Any]) -> bool:
    if demo_mode() or user.get("dev"):
        return True
    return bool(is_pro_user(user))


@router.get("/status", response_model=TradeStatus)
def trade_status(user: Annotated[dict, Depends(require_user)]) -> TradeStatus:
    allowed = _pro_allowed(user)
    return TradeStatus(
        allowed=allowed,
        reason="demo" if demo_mode() or user.get("dev") else pro_gate_reason(user),
        checkout_url=pro_checkout_url(),
        fair_band_pct=float(FAIR_SPOT_BAND_PCT),
    )


@router.post("/score", response_model=TradeResponse)
def trade_score(
    body: TradeRequest,
    user: Annotated[dict, Depends(require_user)],
) -> TradeResponse:
    if not _pro_allowed(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trade Analyzer requires Soft Pro.",
        )
    if not body.you and not body.them:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add at least one card to either side.",
        )
    board, source = load_board()
    if board is None or board.empty:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market board is empty.",
        )
    you = [item.model_dump() for item in body.you]
    them = [item.model_dump() for item in body.them]
    payload = analyze_trade(
        board,
        you=you,
        them=them,
        fair_band_pct=float(body.fair_band_pct if body.fair_band_pct is not None else FAIR_SPOT_BAND_PCT),
    )
    payload["source"] = source
    return TradeResponse(**payload)

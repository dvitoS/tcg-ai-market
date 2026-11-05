"""Trade Analyzer — Soft Pro two-sided deal desk."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from api.catalog_service import load_board
from api.demo_mode import demo_mode
from api.deps import require_user
from api.schemas import (
    TradeRequest,
    TradeResponse,
    TradeShareCreated,
    TradeShareView,
    TradeStatus,
)
from api.trade_service import FAIR_SPOT_BAND_PCT, analyze_trade
from api.trade_share import decode_trade_share, encode_trade_share
from config import get_soft_ink_url
from services.pro import is_pro_user, pro_checkout_url, pro_gate_reason

router = APIRouter(prefix="/trade", tags=["trade"])


def _pro_allowed(user: dict[str, Any]) -> bool:
    if demo_mode() or user.get("dev"):
        return True
    return bool(is_pro_user(user))


def _score_payload(
    *,
    you: list[dict[str, Any]],
    them: list[dict[str, Any]],
    fair_band_pct: float,
) -> dict[str, Any]:
    board, source = load_board()
    if board is None or board.empty:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market board is empty.",
        )
    payload = analyze_trade(
        board,
        you=you,
        them=them,
        fair_band_pct=float(fair_band_pct),
    )
    payload["source"] = source
    return payload


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
    you = [item.model_dump() for item in body.you]
    them = [item.model_dump() for item in body.them]
    payload = _score_payload(
        you=you,
        them=them,
        fair_band_pct=float(
            body.fair_band_pct if body.fair_band_pct is not None else FAIR_SPOT_BAND_PCT
        ),
    )
    return TradeResponse(**payload)


@router.post("/share", response_model=TradeShareCreated)
def trade_share_create(
    body: TradeRequest,
    user: Annotated[dict, Depends(require_user)],
) -> TradeShareCreated:
    """Soft Pro: mint a signed share id for a public read-only view."""
    if not _pro_allowed(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trade share requires Soft Pro.",
        )
    if not body.you and not body.them:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add at least one card to either side.",
        )
    you = [item.model_dump() for item in body.you]
    them = [item.model_dump() for item in body.them]
    try:
        token = encode_trade_share(
            you=you,
            them=them,
            fair_band_pct=float(
                body.fair_band_pct if body.fair_band_pct is not None else FAIR_SPOT_BAND_PCT
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    path = f"/trade/s/{token}"
    base = (get_soft_ink_url() or "").rstrip("/")
    return TradeShareCreated(
        id=token,
        path=path,
        url=f"{base}{path}" if base else None,
    )


@router.get("/share/{share_id:path}", response_model=TradeShareView)
def trade_share_view(share_id: str) -> TradeShareView:
    """Public — verify signature, re-score live against the market board."""
    try:
        decoded = decode_trade_share(share_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc) or "Share not found.",
        ) from exc
    payload = _score_payload(
        you=decoded["you"],
        them=decoded["them"],
        fair_band_pct=float(decoded["fair_band_pct"]),
    )
    return TradeShareView(
        **payload,
        checkout_url=pro_checkout_url(),
        share_id=share_id,
    )

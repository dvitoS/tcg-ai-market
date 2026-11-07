"""Public Soft Ink market pulse for the marketing landing."""

from __future__ import annotations

from fastapi import APIRouter, Query

from api.market_pulse_service import build_market_pulse
from api.schemas import MarketPulseResponse

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/pulse", response_model=MarketPulseResponse)
def market_pulse(
    movers: int = Query(default=5, ge=1, le=8),
) -> MarketPulseResponse:
    """Board breadth + past-7d risers/fallers for Soft Ink home."""
    return MarketPulseResponse(**build_market_pulse(mover_limit=int(movers)))

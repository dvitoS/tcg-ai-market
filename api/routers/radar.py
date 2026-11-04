"""Deal Radar — Soft Pro conformal mispricing desk."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.demo_mode import demo_mode
from api.deps import require_user
from api.radar_service import build_radar, radar_defaults
from api.schemas import RadarResponse, RadarStatus
from services.pro import is_pro_user, pro_checkout_url, pro_gate_reason

router = APIRouter(prefix="/radar", tags=["radar"])


def _pro_allowed(user: dict[str, Any]) -> bool:
    if demo_mode() or user.get("dev"):
        return True
    return bool(is_pro_user(user))


@router.get("/status", response_model=RadarStatus)
def radar_status(user: Annotated[dict, Depends(require_user)]) -> RadarStatus:
    allowed = _pro_allowed(user)
    defaults = radar_defaults()
    return RadarStatus(
        allowed=allowed,
        reason="demo" if demo_mode() or user.get("dev") else pro_gate_reason(user),
        checkout_url=pro_checkout_url(),
        forecast_days=int(defaults["forecast_days"]),
        edge_floor=float(defaults["edge_floor"]),
    )


@router.get("", response_model=RadarResponse)
def radar_board(
    user: Annotated[dict, Depends(require_user)],
    q: str | None = Query(default=None),
    set_name: str | None = Query(default=None, alias="set"),
    rarity: str | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    min_edge: float | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=24, ge=1, le=100),
) -> RadarResponse:
    if not _pro_allowed(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Deal Radar requires Soft Pro.",
        )
    defaults = radar_defaults()
    edge = float(min_edge) if min_edge is not None else float(defaults["edge_floor"])
    payload = build_radar(
        q=q,
        set_name=set_name,
        rarity=rarity,
        min_price=min_price,
        max_price=max_price,
        min_edge=edge,
        limit=limit,
    )
    return RadarResponse(**payload)

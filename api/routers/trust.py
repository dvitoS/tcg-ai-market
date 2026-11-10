"""Model trust panel — Kestrel Pro calibration + coverage + radar-call hits."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api.demo_mode import demo_mode
from api.deps import require_user
from api.schemas import (
    TrustCalibration,
    TrustCoverage,
    TrustRadarBacktest,
    TrustResponse,
    TrustStatus,
)
from api.trust_service import build_trust_report
from services.pro import is_pro_user, pro_checkout_url, pro_gate_reason

router = APIRouter(prefix="/trust", tags=["trust"])

_NO_STORE = {"Cache-Control": "no-store"}


def _pro_allowed(user: dict[str, Any]) -> bool:
    if demo_mode() or user.get("dev"):
        return True
    return bool(is_pro_user(user))


@router.get("/status", response_model=TrustStatus)
def trust_status(
    user: Annotated[dict, Depends(require_user)],
    response: Response,
) -> TrustStatus:
    response.headers.update(_NO_STORE)
    allowed = _pro_allowed(user)
    return TrustStatus(
        allowed=allowed,
        reason="demo" if demo_mode() or user.get("dev") else pro_gate_reason(user),
        checkout_url=pro_checkout_url(),
    )


@router.get("", response_model=TrustResponse)
def trust_report(
    user: Annotated[dict, Depends(require_user)],
    response: Response,
    horizon_days: int = Query(default=7, ge=3, le=30),
    lookback_days: int = Query(default=30, ge=7, le=120),
    sample_n: int = Query(default=80, ge=10, le=120),
    min_edge: float = Query(
        default=0,
        ge=0,
        le=100,
        description="Same % floor as Radar min edge — scores only tips at/above it.",
    ),
) -> TrustResponse:
    response.headers.update(_NO_STORE)
    if not _pro_allowed(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Model trust requires Kestrel Pro.",
        )
    payload = build_trust_report(
        horizon_days=horizon_days,
        lookback_days=lookback_days,
        sample_n=sample_n,
        min_edge=min_edge,
    )
    return TrustResponse(
        source=payload.get("source") or "empty",
        trained_at=payload.get("trained_at"),
        artifact_id=str(payload.get("artifact_id") or "latest"),
        horizon_days=int(payload.get("horizon_days") or horizon_days),
        min_edge=float(payload.get("min_edge") or min_edge or 0),
        calibration=TrustCalibration(**(payload.get("calibration") or {})),
        conformal_coverage=TrustCoverage(**(payload.get("conformal_coverage") or {})),
        radar_backtest=TrustRadarBacktest(**(payload.get("radar_backtest") or {})),
    )

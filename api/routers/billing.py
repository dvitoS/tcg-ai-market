"""Kestrel Pro / Creem billing status (no secrets)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from api.deps import optional_user, require_ops_user
from api.schemas import TrialConversionResponse
from services.pro import billing_snapshot, pro_checkout_url, pro_open_beta
from services.pro_entitlements import conversion_summary

router = APIRouter(tags=["billing"])

_NO_STORE = {"Cache-Control": "no-store"}


@router.get("/billing/status")
def billing_status() -> dict[str, Any]:
    """Anonymous shop status — open beta flag + checkout link only."""
    return {
        "pro_open": bool(pro_open_beta()),
        "checkout_url": pro_checkout_url(),
    }


@router.get("/billing/me")
def billing_me(
    user: Annotated[dict[str, Any] | None, Depends(optional_user)],
) -> dict[str, Any]:
    """Per-session Kestrel Pro status (is_pro, reason, portal/checkout)."""
    return billing_snapshot(user)


@router.get("/billing/conversion", response_model=TrialConversionResponse)
def billing_conversion(
    _ops: Annotated[dict[str, Any], Depends(require_ops_user)],
    response: Response,
) -> TrialConversionResponse:
    """Ops dashboard: trial vs paid entitlement counts + webhook outcomes."""
    response.headers.update(_NO_STORE)
    return TrialConversionResponse(**conversion_summary())

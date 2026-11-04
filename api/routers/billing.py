"""Soft Pro / Creem billing status (no secrets)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from api.deps import optional_user
from services.pro import billing_snapshot, pro_checkout_url, pro_open_beta

router = APIRouter(tags=["billing"])


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
    """Per-session Soft Pro status (is_pro, reason, portal/checkout)."""
    return billing_snapshot(user)

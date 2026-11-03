"""Public Soft Pro / Creem billing status (no secrets)."""

from __future__ import annotations

from fastapi import APIRouter

from services.pro import pro_checkout_url, pro_open_beta

router = APIRouter(tags=["billing"])


@router.get("/billing/status")
def billing_status() -> dict:
    return {
        "pro_open": bool(pro_open_beta()),
        "checkout_url": pro_checkout_url(),
    }

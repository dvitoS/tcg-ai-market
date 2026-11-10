"""PSA Public API — cert + population (Grading EV gem-rate assist)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from api.schemas import PsaCertLookupResponse
from psa_public_client import (
    PsaPublicError,
    PsaPublicRateLimitError,
    lookup_cert_pack,
    psa_public_configured,
)

router = APIRouter(tags=["psa"])


@router.get("/psa/cert/{cert_number}", response_model=PsaCertLookupResponse)
def psa_cert_lookup(
    cert_number: str,
    include_pop: bool = Query(True, description="Also fetch SpecID population"),
) -> PsaCertLookupResponse:
    """Look up a PSA cert. No market prices — JustTCG still owns graded comps."""
    if not psa_public_configured():
        raise HTTPException(
            status_code=503,
            detail="PSA Public API not configured (set PSA_PUBLIC_API_TOKEN).",
        )
    try:
        pack = lookup_cert_pack(cert_number, include_pop=include_pop)
    except PsaPublicRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except PsaPublicError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PsaCertLookupResponse(**pack)


@router.get("/psa/status")
def psa_status() -> dict[str, Any]:
    return {
        "configured": psa_public_configured(),
        "provides_market_prices": False,
        "note": (
            "Cert + population only. Soft Ink PSA 9/10 comps still come from JustTCG."
        ),
    }

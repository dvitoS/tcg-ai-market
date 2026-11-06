"""Public FX quote for Soft Ink EUR spot display."""

from __future__ import annotations

from fastapi import APIRouter

from api.fx_service import get_usd_eur_quote
from api.schemas import FxQuoteResponse

router = APIRouter(tags=["fx"])


@router.get("/fx", response_model=FxQuoteResponse)
def fx_quote() -> FxQuoteResponse:
    payload = get_usd_eur_quote()
    return FxQuoteResponse(
        usd_eur=float(payload["usd_eur"]),
        as_of=payload.get("as_of"),
        source=str(payload.get("source") or "fallback"),
        fallback=bool(payload.get("fallback")),
    )

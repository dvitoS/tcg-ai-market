"""Public AI Scanner endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Query

from api.scanner_service import build_scanner, scanner_defaults
from api.schemas import ScannerResponse

router = APIRouter(tags=["scanner"])


@router.get("/scanner", response_model=ScannerResponse)
def scanner(
    q: str | None = Query(default=None),
    set_name: str | None = Query(default=None, alias="set"),
    rarity: str | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    min_growth: float | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=24, ge=1, le=100),
) -> ScannerResponse:
    defaults = scanner_defaults()
    growth = float(min_growth) if min_growth is not None else float(defaults["growth_floor"])
    payload = build_scanner(
        q=q,
        set_name=set_name,
        rarity=rarity,
        min_price=min_price,
        max_price=max_price,
        min_growth=growth,
        limit=limit,
    )
    return ScannerResponse(**payload)

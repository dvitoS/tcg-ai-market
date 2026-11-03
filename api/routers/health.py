"""Health / readiness."""

from __future__ import annotations

from fastapi import APIRouter

from api.catalog_service import load_board
from api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    _, source = load_board()
    return HealthResponse(status="ok", source=source)

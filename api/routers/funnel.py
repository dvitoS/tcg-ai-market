"""Soft-launch funnel ingest + ops summary."""

from __future__ import annotations

from fastapi import APIRouter, Response

from api.schemas import FunnelBatchIn, FunnelBatchOut, FunnelSummaryResponse
from services.funnel import funnel_summary, record_events

router = APIRouter(prefix="/funnel", tags=["funnel"])

_NO_STORE = {"Cache-Control": "no-store"}


@router.post("/events", response_model=FunnelBatchOut)
def post_funnel_events(body: FunnelBatchIn, response: Response) -> FunnelBatchOut:
    response.headers.update(_NO_STORE)
    payload = [
        {
            "event": item.event,
            "session": item.session,
            "props": item.props,
        }
        for item in (body.events or [])[:20]
    ]
    result = record_events(payload)
    return FunnelBatchOut(**result)


@router.get("/summary", response_model=FunnelSummaryResponse)
def get_funnel_summary(response: Response) -> FunnelSummaryResponse:
    """Soft-launch funnel counters (persisted across API restarts)."""
    response.headers.update(_NO_STORE)
    return FunnelSummaryResponse(**funnel_summary())

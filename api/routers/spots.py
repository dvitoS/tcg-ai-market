"""Wrong-spot reports (public submit + ops queue)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from api.deps import optional_user, require_ops_user
from api.schemas import SpotHealResponse
from services.spot_reports import (
    list_spot_reports,
    open_report_card_ids,
    set_report_status,
    spot_report_summary,
    submit_spot_report,
)

router = APIRouter(prefix="/spots", tags=["spots"])

_NO_STORE = {"Cache-Control": "no-store"}


class SpotReportIn(BaseModel):
    card_id: str = Field(min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=280)
    spot: float | None = None
    session: str | None = Field(default=None, max_length=64)


class SpotReportOut(BaseModel):
    id: str
    card_id: str
    note: str | None = None
    spot: float | None = None
    session: str | None = None
    status: str
    created_at: float
    updated_at: float


class SpotReportSummaryOut(BaseModel):
    counts: dict[str, int] = Field(default_factory=dict)
    open_total: int = 0
    oldest_open_age_h: float | None = None
    overdue_ack: int = 0
    overdue_heal: int = 0
    ack_sla_hours: int = 24
    heal_sla_hours: int = 48
    recent: list[dict[str, Any]] = Field(default_factory=list)
    uptime_s: float = 0.0


class SpotReportStatusIn(BaseModel):
    status: Literal["open", "acked", "resolved", "dismissed"]


@router.post("/report", response_model=SpotReportOut)
def post_spot_report(
    body: SpotReportIn,
    response: Response,
    _user: Annotated[dict[str, Any] | None, Depends(optional_user)] = None,
) -> SpotReportOut:
    """Anyone can flag a wrong desk spot (soft-launch support intake)."""
    response.headers.update(_NO_STORE)
    try:
        row = submit_spot_report(
            card_id=body.card_id,
            note=body.note,
            spot=body.spot,
            session=body.session,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return SpotReportOut(**row)


@router.get("/reports", response_model=list[SpotReportOut])
def get_spot_reports(
    _ops: Annotated[dict[str, Any], Depends(require_ops_user)],
    response: Response,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=40, ge=1, le=100),
) -> list[SpotReportOut]:
    response.headers.update(_NO_STORE)
    rows = list_spot_reports(status=status_filter, limit=limit)
    return [SpotReportOut(**row) for row in rows]


@router.get("/reports/summary", response_model=SpotReportSummaryOut)
def get_spot_report_summary(
    _ops: Annotated[dict[str, Any], Depends(require_ops_user)],
    response: Response,
) -> SpotReportSummaryOut:
    response.headers.update(_NO_STORE)
    return SpotReportSummaryOut(**spot_report_summary())


@router.post("/reports/{report_id}/status", response_model=SpotReportOut)
def patch_spot_report_status(
    report_id: str,
    body: SpotReportStatusIn,
    _ops: Annotated[dict[str, Any], Depends(require_ops_user)],
    response: Response,
) -> SpotReportOut:
    response.headers.update(_NO_STORE)
    row = set_report_status(report_id, body.status)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return SpotReportOut(**row)


@router.post("/reports/heal-open", response_model=SpotHealResponse)
def heal_open_spot_reports(
    _ops: Annotated[dict[str, Any], Depends(require_ops_user)],
    response: Response,
    mode: Literal["dry_run", "null_market", "clear_history", "refetch"] = Query(
        default="dry_run"
    ),
    limit: int = Query(default=30, ge=1, le=100),
) -> SpotHealResponse:
    """Ops: heal currently open/acked reported card ids (same heal pipeline)."""
    from api.catalog_service import clear_board_cache
    from api.price_sources_service import clear_price_sources_cache
    from services.spot_heal import heal_poisoned_spots

    response.headers.update(_NO_STORE)
    ids = open_report_card_ids(limit=limit)
    if not ids:
        return SpotHealResponse(mode=mode, count=0, ids=[])
    result = heal_poisoned_spots(mode=mode, limit=limit, card_ids=ids)
    if mode != "dry_run":
        clear_board_cache()
        clear_price_sources_cache()
        # Mark matching open reports resolved when we actually mutated.
        for row in list_spot_reports(status="open", limit=100) + list_spot_reports(
            status="acked", limit=100
        ):
            if str(row.get("card_id")) in set(ids):
                set_report_status(str(row["id"]), "resolved")
    return SpotHealResponse(
        mode=str(result.get("mode") or mode),
        count=int(result.get("count") or 0),
        ids=list(result.get("ids") or [])[:50],
        poison_keys=[float(x) for x in list(result.get("poison_keys") or [])],
        nulled=int(result.get("nulled") or 0),
        history_cleared=int(result.get("history_cleared") or 0),
        quotes_quarantined=int(result.get("quotes_quarantined") or 0),
        updated=int(result.get("updated") or 0),
        skipped=int(result.get("skipped") or 0),
        skip_poison=int(result.get("skip_poison") or 0),
        skip_absurd=int(result.get("skip_absurd") or 0),
        saved=int(result.get("saved") or 0),
    )

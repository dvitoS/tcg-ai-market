"""Set completion / binder checklist (Soft Ink)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from api.binder_service import binder_for_set, binder_sets
from api.deps import require_user
from api.portfolio_service import bearer_from_authorization
from api.schemas import (
    BinderMissingCard,
    BinderResponse,
    BinderSetSummary,
    BinderSetsResponse,
)

router = APIRouter(prefix="/binder", tags=["binder"])


@router.get("/sets", response_model=BinderSetsResponse)
def list_binder_sets(
    user: Annotated[dict, Depends(require_user)],
    authorization: Annotated[str | None, Header()] = None,
) -> BinderSetsResponse:
    token = bearer_from_authorization(authorization)
    payload = binder_sets(user_id=str(user["id"]), access_token=token)
    return BinderSetsResponse(
        sets=[BinderSetSummary(**row) for row in payload.get("sets") or []],
        source=payload.get("source") or "empty",
        demo=bool(payload.get("demo")),
    )


@router.get("", response_model=BinderResponse)
def binder_checklist(
    user: Annotated[dict, Depends(require_user)],
    authorization: Annotated[str | None, Header()] = None,
    set_name: str = Query(..., min_length=1, max_length=160),
    missing_limit: int = Query(default=120, ge=1, le=400),
) -> BinderResponse:
    token = bearer_from_authorization(authorization)
    payload = binder_for_set(
        user_id=str(user["id"]),
        set_name=set_name,
        access_token=token,
        missing_limit=missing_limit,
    )
    if payload.get("total", 0) <= 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No catalog cards for set {set_name!r}.",
        )
    return BinderResponse(
        set_name=str(payload["set_name"]),
        set_id=payload.get("set_id"),
        total=int(payload["total"]),
        owned=int(payload["owned"]),
        missing=int(payload["missing"]),
        pct_complete=float(payload["pct_complete"]),
        missing_cost=float(payload["missing_cost"]),
        missing_unpriced=int(payload["missing_unpriced"]),
        owned_ids=list(payload.get("owned_ids") or []),
        missing_cards=[
            BinderMissingCard(**row) for row in payload.get("missing_cards") or []
        ],
        source=payload.get("source") or "empty",
        demo=bool(payload.get("demo")),
    )

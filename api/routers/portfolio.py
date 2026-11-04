"""Authenticated portfolio + watchlist routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from api.demo_mode import demo_mode
from api.deps import require_user
from api.portfolio_service import (
    add_lot,
    add_watch,
    bearer_from_authorization,
    delete_lot,
    is_watched,
    list_portfolio,
    list_watchlist,
    portfolio_summary,
    remove_watch,
)
from api.schemas import (
    AddLotRequest,
    AddWatchRequest,
    PortfolioLot,
    PortfolioResponse,
    PortfolioSummary,
    WatchlistItem,
    WatchlistResponse,
)

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio(
    user: Annotated[dict, Depends(require_user)],
    authorization: Annotated[str | None, Header()] = None,
    include_sold: bool = Query(default=False),
) -> PortfolioResponse:
    token = bearer_from_authorization(authorization)
    try:
        items = list_portfolio(
            user_id=str(user["id"]),
            include_sold=include_sold,
            access_token=token,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Portfolio unavailable: {exc}",
        ) from exc
    summary = PortfolioSummary(**portfolio_summary(items))
    return PortfolioResponse(
        items=[PortfolioLot(**row) for row in items],
        summary=summary,
        demo=demo_mode(),
    )


@router.post("/portfolio/lots", response_model=PortfolioLot, status_code=201)
def create_lot(
    body: AddLotRequest,
    user: Annotated[dict, Depends(require_user)],
    authorization: Annotated[str | None, Header()] = None,
) -> PortfolioLot:
    token = bearer_from_authorization(authorization)
    try:
        lot = add_lot(
            user_id=str(user["id"]),
            card_id=body.card_id,
            quantity=body.quantity,
            purchase_price=body.purchase_price,
            condition=body.condition,
            grade=body.grade,
            purchase_date=body.purchase_date,
            access_token=token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not add lot: {exc}",
        ) from exc
    return PortfolioLot(**lot)


@router.delete("/portfolio/lots/{entry_id}")
def remove_lot(
    entry_id: int,
    user: Annotated[dict, Depends(require_user)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    token = bearer_from_authorization(authorization)
    ok = delete_lot(user_id=str(user["id"]), entry_id=entry_id, access_token=token)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lot not found.")
    return {"ok": True}


@router.get("/watchlist", response_model=WatchlistResponse)
def get_watchlist(
    user: Annotated[dict, Depends(require_user)],
    authorization: Annotated[str | None, Header()] = None,
) -> WatchlistResponse:
    token = bearer_from_authorization(authorization)
    try:
        items = list_watchlist(user_id=str(user["id"]), access_token=token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Watchlist unavailable: {exc}",
        ) from exc
    return WatchlistResponse(
        items=[WatchlistItem(**row) for row in items],
        demo=demo_mode(),
    )


@router.post("/watchlist", response_model=WatchlistItem, status_code=201)
def create_watch(
    body: AddWatchRequest,
    user: Annotated[dict, Depends(require_user)],
    authorization: Annotated[str | None, Header()] = None,
) -> WatchlistItem:
    token = bearer_from_authorization(authorization)
    try:
        row = add_watch(user_id=str(user["id"]), card_id=body.card_id, access_token=token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not add watch: {exc}",
        ) from exc
    return WatchlistItem(**row)


@router.delete("/watchlist/{card_id}")
def delete_watch(
    card_id: str,
    user: Annotated[dict, Depends(require_user)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    token = bearer_from_authorization(authorization)
    ok = remove_watch(user_id=str(user["id"]), card_id=card_id, access_token=token)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watch item not found.")
    return {"ok": True}


@router.get("/watchlist/{card_id}/status")
def watch_status(
    card_id: str,
    user: Annotated[dict, Depends(require_user)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    token = bearer_from_authorization(authorization)
    try:
        return {
            "watched": is_watched(
                user_id=str(user["id"]),
                card_id=card_id,
                access_token=token,
            )
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Watch status unavailable: {exc}",
        ) from exc

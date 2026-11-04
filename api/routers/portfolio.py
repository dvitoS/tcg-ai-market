"""Authenticated portfolio + watchlist routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from api.alerts_service import collect_user_watchlist_alerts
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
    sell_lot,
    update_lot,
)
from api.schemas import (
    AddLotRequest,
    AddWatchRequest,
    PortfolioLot,
    PortfolioResponse,
    PortfolioSummary,
    SellLotRequest,
    UpdateLotRequest,
    WatchAlertItem,
    WatchAlertsResponse,
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


@router.patch("/portfolio/lots/{entry_id}", response_model=PortfolioLot)
def patch_lot(
    entry_id: int,
    body: UpdateLotRequest,
    user: Annotated[dict, Depends(require_user)],
    authorization: Annotated[str | None, Header()] = None,
) -> PortfolioLot:
    token = bearer_from_authorization(authorization)
    try:
        lot = update_lot(
            user_id=str(user["id"]),
            entry_id=entry_id,
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
            detail=f"Could not update lot: {exc}",
        ) from exc
    if lot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lot not found.")
    return PortfolioLot(**lot)


@router.post("/portfolio/lots/{entry_id}/sell", response_model=PortfolioLot)
def mark_lot_sold(
    entry_id: int,
    body: SellLotRequest,
    user: Annotated[dict, Depends(require_user)],
    authorization: Annotated[str | None, Header()] = None,
) -> PortfolioLot:
    token = bearer_from_authorization(authorization)
    try:
        lot = sell_lot(
            user_id=str(user["id"]),
            entry_id=entry_id,
            sale_price=body.sale_price,
            sale_date=body.sale_date,
            access_token=token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not sell lot: {exc}",
        ) from exc
    if lot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lot not found.")
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


@router.get("/watchlist/alerts", response_model=WatchAlertsResponse)
def get_watchlist_alerts(
    user: Annotated[dict, Depends(require_user)],
    authorization: Annotated[str | None, Header()] = None,
    threshold_pct: float = Query(default=5.0, ge=1.0, le=50.0),
    sure_only: bool = Query(default=True),
    dismissed: str | None = Query(
        default=None,
        description="Comma-separated card ids to hide from the digest.",
    ),
) -> WatchAlertsResponse:
    token = bearer_from_authorization(authorization)
    dismissed_ids = [part.strip() for part in (dismissed or "").split(",") if part.strip()]
    try:
        payload = collect_user_watchlist_alerts(
            user_id=str(user["id"]),
            threshold_pct=threshold_pct,
            sure_only=sure_only,
            access_token=token,
            dismissed=dismissed_ids,
            user=user,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Watchlist alerts unavailable: {exc}",
        ) from exc
    return WatchAlertsResponse(
        items=[WatchAlertItem(**row) for row in payload["items"]],
        threshold_pct=float(payload["threshold_pct"]),
        sure_only=bool(payload["sure_only"]),
        sure_only_allowed=bool(payload["sure_only_allowed"]),
        watch_count=int(payload["watch_count"]),
        demo=bool(payload["demo"]),
        source=payload["source"],
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

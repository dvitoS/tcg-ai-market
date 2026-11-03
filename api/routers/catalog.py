"""Public catalog browse + AI signals board."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from api.catalog_service import board_meta, filter_board, load_board, row_to_card
from api.schemas import CatalogCard, CatalogMeta, CatalogResponse, SignalBoardResponse

router = APIRouter(tags=["catalog"])


@router.get("/catalog", response_model=CatalogResponse)
def catalog(
    q: str | None = Query(default=None, description="Search name / set / id"),
    set_name: str | None = Query(default=None, alias="set"),
    signal: str | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    mode: Literal["browse", "signals"] = Query(default="browse"),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: Literal["price_desc", "price_asc", "change_desc", "change_asc", "name"] = Query(
        default="price_desc"
    ),
) -> CatalogResponse:
    board, source = load_board()
    meta = CatalogMeta(**board_meta(board, source))
    filtered = filter_board(
        board,
        q=q,
        set_name=set_name,
        signal=signal,
        min_price=min_price,
        max_price=max_price,
        mode=mode,
    )
    if filtered is None or filtered.empty:
        return CatalogResponse(items=[], total=0, limit=limit, offset=offset, meta=meta)

    sort_map = {
        "price_desc": ("price", False),
        "price_asc": ("price", True),
        "change_desc": ("expected_change_pct", False),
        "change_asc": ("expected_change_pct", True),
        "name": ("name", True),
    }
    col, ascending = sort_map[sort]
    if col in filtered.columns:
        filtered = filtered.sort_values(col, ascending=ascending, na_position="last")

    total = int(len(filtered))
    page = filtered.iloc[offset : offset + limit]
    items = [CatalogCard(**row_to_card(row)) for _, row in page.iterrows()]
    return CatalogResponse(items=items, total=total, limit=limit, offset=offset, meta=meta)


@router.get("/catalog/meta", response_model=CatalogMeta)
def catalog_meta() -> CatalogMeta:
    board, source = load_board()
    return CatalogMeta(**board_meta(board, source))


@router.get("/signals", response_model=SignalBoardResponse)
def signals(limit: int = Query(default=12, ge=1, le=48)) -> SignalBoardResponse:
    board, source = load_board()
    if board is None or board.empty or "signal" not in board.columns:
        return SignalBoardResponse(buys=[], sells=[], holds=[], source=source)

    frame = board
    if "confidence_ok" in frame.columns:
        sure = frame[frame["confidence_ok"]]
        if not sure.empty:
            frame = sure

    def _top(sig: str) -> list[CatalogCard]:
        subset = frame[frame["signal"].astype(str).str.upper() == sig]
        if "expected_change_pct" in subset.columns:
            ascending = sig == "SELL"
            subset = subset.sort_values(
                "expected_change_pct", ascending=ascending, na_position="last"
            )
        return [CatalogCard(**row_to_card(row)) for _, row in subset.head(limit).iterrows()]

    return SignalBoardResponse(
        buys=_top("BUY"),
        sells=_top("SELL"),
        holds=_top("HOLD"),
        source=source,
    )

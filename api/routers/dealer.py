"""Dealer desk — CSV inventory × fee-aware AI actions."""

from __future__ import annotations

from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status

from api.catalog_service import load_board
from api.demo_mode import demo_mode
from api.deps import require_user
from api.schemas import DealerRequest, DealerResponse, DealerRow
from services.dealer_desk import (
    ACTION_BUY_MORE,
    ACTION_LIST,
    DEFAULT_SELL_FEE_PCT,
    DEFAULT_SHIP_USD,
    build_dealer_board,
    parse_inventory_csv,
)
from services.pro import is_pro_user, pro_checkout_url, pro_gate_reason

router = APIRouter(prefix="/dealer", tags=["dealer"])


def _pro_allowed(user: dict[str, Any]) -> bool:
    if demo_mode() or user.get("dev"):
        return True
    return bool(is_pro_user(user))


@router.get("/status")
def dealer_status(user: Annotated[dict, Depends(require_user)]) -> dict[str, Any]:
    allowed = _pro_allowed(user)
    return {
        "allowed": allowed,
        "reason": "demo" if demo_mode() or user.get("dev") else pro_gate_reason(user),
        "checkout_url": pro_checkout_url(),
        "default_fee_pct": DEFAULT_SELL_FEE_PCT,
        "default_ship_usd": DEFAULT_SHIP_USD,
        "sample_csv": "card_id,quantity,cost\nsv1-1,2,3.20\nsv1-45,1,1.70\nsv1-32,1,1.40\n",
    }


@router.post("/score", response_model=DealerResponse)
def dealer_score(
    body: DealerRequest,
    user: Annotated[dict, Depends(require_user)],
) -> DealerResponse:
    if not _pro_allowed(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dealer desk requires Kestrel Pro.",
        )
    try:
        inventory = parse_inventory_csv(body.csv_text)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse CSV: {exc}",
        ) from exc
    if inventory.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV has no usable rows.",
        )

    board, source = load_board()
    if board is None or board.empty:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market board is empty.",
        )

    fee = float(body.fee_pct if body.fee_pct is not None else DEFAULT_SELL_FEE_PCT)
    ship = float(body.ship_usd if body.ship_usd is not None else DEFAULT_SHIP_USD)
    try:
        scored = build_dealer_board(inventory, board, fee_pct=fee, ship_usd=ship)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)[:220],
        ) from exc

    unmatched = int(scored.attrs.get("unmatched") or 0) if scored is not None else 0
    rows: list[dict[str, Any]] = []
    if scored is not None and not scored.empty:
        for _, row in scored.iterrows():
            payload = {k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in row.items()}
            # Normalize numpy types
            for key in ("quantity",):
                if payload.get(key) is not None:
                    payload[key] = int(payload[key])
            for key in (
                "unit_cost",
                "spot",
                "expected_change_pct",
                "pred_lo_pct",
                "pred_hi_pct",
                "net_now",
                "net_forecast",
                "net_edge_pct",
                "inventory_value",
            ):
                if payload.get(key) is not None:
                    payload[key] = float(payload[key])
            payload["matched"] = bool(payload.get("matched"))
            payload["conformal_ok"] = bool(payload.get("conformal_ok"))
            rows.append(payload)

    matched_n = sum(1 for r in rows if r.get("matched"))
    actionable_n = sum(1 for r in rows if r.get("action") in {ACTION_LIST, ACTION_BUY_MORE})
    inventory_value = float(
        sum(float(r.get("inventory_value") or 0.0) for r in rows if r.get("matched"))
    )

    return DealerResponse(
        items=[DealerRow(**r) for r in rows],
        rows=len(inventory),
        matched=matched_n,
        actionable=actionable_n,
        unmatched=unmatched,
        inventory_value=inventory_value,
        fee_pct=fee,
        ship_usd=ship,
        source=source,
        demo=demo_mode(),
    )

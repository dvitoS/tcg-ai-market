"""Set completion / binder checklist over the Soft Ink board + portfolio."""

from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd

from api.catalog_service import filter_board, load_board, row_to_card
from api.demo_mode import demo_mode
from api.portfolio_service import list_portfolio


def _card_number(card_id: str) -> str:
    if "-" not in card_id:
        return ""
    return card_id.rsplit("-", 1)[-1]


def _set_id(card_id: str) -> str | None:
    if "-" not in card_id:
        return None
    prefix = card_id.rsplit("-", 1)[0].strip()
    return prefix or None


def _number_sort_key(card_id: str) -> tuple[int, str]:
    num = _card_number(card_id)
    digits = re.sub(r"\D", "", num)
    try:
        return (int(digits) if digits else 10**9, num.lower())
    except ValueError:
        return (10**9, num.lower())


def _finite_price(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num) or num <= 0:
        return None
    return num


def _owned_ids(user_id: str, access_token: str | None) -> set[str]:
    lots = list_portfolio(
        user_id=user_id,
        include_sold=False,
        access_token=access_token,
    )
    out: set[str] = set()
    for lot in lots:
        if str(lot.get("status") or "open").lower() == "sold":
            continue
        try:
            qty = int(lot.get("quantity") or 0)
        except (TypeError, ValueError):
            qty = 0
        if qty < 1:
            continue
        cid = str(lot.get("card_id") or "").strip()
        if cid and not cid.startswith("sealed:"):
            out.add(cid)
    return out


def _set_frame(set_name: str) -> tuple[pd.DataFrame, str]:
    board, source = load_board()
    scoped = filter_board(board, set_name=set_name, mode="browse")
    return scoped if scoped is not None else pd.DataFrame(), source


def binder_sets(*, user_id: str, access_token: str | None = None) -> dict[str, Any]:
    board, source = load_board()
    owned = _owned_ids(user_id, access_token)
    if board is None or board.empty:
        return {"sets": [], "source": source or "empty", "demo": demo_mode()}

    frame = board.copy()
    frame["_id"] = frame["id"].astype(str)
    set_col = frame.get("set_name", pd.Series("", index=frame.index)).astype(str).str.strip()
    frame["_set"] = set_col
    frame = frame.loc[frame["_set"].ne("") & frame["_set"].notna()].copy()
    if frame.empty:
        return {"sets": [], "source": source, "demo": demo_mode()}

    price_col = frame["price"] if "price" in frame.columns else frame.get("market_price")
    prices = pd.to_numeric(price_col, errors="coerce")
    owned_mask = frame["_id"].isin(owned)
    miss_cost = prices.where(~owned_mask & prices.gt(0), 0.0).fillna(0.0)
    frame = frame.assign(_owned=owned_mask, _miss_cost=miss_cost)

    summaries: list[dict[str, Any]] = []
    for set_name, group in frame.groupby("_set", sort=False):
        total = int(len(group))
        if total <= 0:
            continue
        have = int(group["_owned"].sum())
        first_id = str(group["_id"].iloc[0])
        summaries.append(
            {
                "set_name": str(set_name),
                "set_id": _set_id(first_id),
                "total": total,
                "owned": have,
                "missing": max(0, total - have),
                "pct": round(100.0 * have / total, 1) if total else 0.0,
                "missing_cost": round(float(group["_miss_cost"].sum()), 2),
            }
        )
    summaries.sort(key=lambda s: (-float(s["pct"]), s["set_name"]))
    return {"sets": summaries, "source": source, "demo": demo_mode()}


def binder_for_set(
    *,
    user_id: str,
    set_name: str,
    access_token: str | None = None,
    missing_limit: int = 120,
) -> dict[str, Any]:
    set_name = str(set_name or "").strip()
    missing_limit = max(1, min(int(missing_limit or 120), 400))
    scoped, source = _set_frame(set_name)
    owned = _owned_ids(user_id, access_token)
    if scoped is None or scoped.empty:
        return {
            "set_name": set_name,
            "set_id": None,
            "total": 0,
            "owned": 0,
            "missing": 0,
            "pct_complete": 0.0,
            "missing_cost": 0.0,
            "missing_unpriced": 0,
            "owned_ids": [],
            "missing_cards": [],
            "source": source or "empty",
            "demo": demo_mode(),
        }

    ids = [str(x) for x in scoped["id"].astype(str).tolist()]
    owned_in_set = sorted([cid for cid in ids if cid in owned])
    missing_rows = []
    missing_cost = 0.0
    missing_unpriced = 0
    for _, row in scoped.iterrows():
        card = row_to_card(row)
        cid = str(card["id"])
        if cid in owned:
            continue
        price = _finite_price(card.get("price") or card.get("market_price"))
        if price is None:
            missing_unpriced += 1
        else:
            missing_cost += price
        missing_rows.append(
            {
                "id": cid,
                "name": card.get("name") or cid,
                "number": _card_number(cid) or None,
                "rarity": card.get("rarity"),
                "price": price,
                "image_url": card.get("image_url"),
            }
        )
    missing_rows.sort(key=lambda r: _number_sort_key(str(r["id"])))
    total = len(ids)
    have = len(owned_in_set)
    return {
        "set_name": set_name,
        "set_id": _set_id(ids[0]) if ids else None,
        "total": total,
        "owned": have,
        "missing": max(0, total - have),
        "pct_complete": round(100.0 * have / total, 1) if total else 0.0,
        "missing_cost": round(missing_cost, 2),
        "missing_unpriced": missing_unpriced,
        "owned_ids": owned_in_set,
        "missing_cards": missing_rows[:missing_limit],
        "source": source,
        "demo": demo_mode(),
    }

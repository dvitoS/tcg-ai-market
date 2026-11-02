"""Dealer desk: CSV inventory × market AI board, fee-aware ranking."""

from __future__ import annotations

import io
from typing import Any

import numpy as np
import pandas as pd

from trading_signals import FORECAST_SIGNAL_BAND, SIGNAL_BUY, SIGNAL_HOLD, SIGNAL_SELL

# Rough marketplace defaults (editable in UI).
DEFAULT_SELL_FEE_PCT = 13.0
DEFAULT_SHIP_USD = 4.0

ACTION_LIST = "LIST"
ACTION_BUY_MORE = "BUY_MORE"
ACTION_HOLD = "HOLD"

_ID_ALIASES = ("card_id", "id", "sku", "product_id", "tcg_id")
_NAME_ALIASES = ("name", "card", "card_name", "title")
_QTY_ALIASES = ("qty", "quantity", "count", "units")
_COST_ALIASES = ("cost", "purchase_price", "buy_price", "unit_cost", "price_paid")


def _pick_column(columns: list[str], aliases: tuple[str, ...]) -> str | None:
    lower = {c.lower().strip(): c for c in columns}
    for alias in aliases:
        if alias in lower:
            return lower[alias]
    return None


def parse_inventory_csv(raw: bytes | str) -> pd.DataFrame:
    """Parse dealer CSV into normalized rows: card_id?, name?, quantity, unit_cost?."""
    text = raw.decode("utf-8-sig") if isinstance(raw, (bytes, bytearray)) else str(raw)
    frame = pd.read_csv(io.StringIO(text))
    if frame.empty:
        return pd.DataFrame(columns=["card_id", "name", "quantity", "unit_cost"])

    cols = [str(c) for c in frame.columns]
    id_col = _pick_column(cols, _ID_ALIASES)
    name_col = _pick_column(cols, _NAME_ALIASES)
    qty_col = _pick_column(cols, _QTY_ALIASES)
    cost_col = _pick_column(cols, _COST_ALIASES)
    if id_col is None and name_col is None:
        raise ValueError("CSV needs a card_id/id or name column.")

    out = pd.DataFrame()
    out["card_id"] = (
        frame[id_col].astype(str).str.strip() if id_col else ""
    )
    out["name"] = (
        frame[name_col].astype(str).str.strip() if name_col else ""
    )
    if qty_col:
        out["quantity"] = pd.to_numeric(frame[qty_col], errors="coerce").fillna(1).clip(lower=1)
    else:
        out["quantity"] = 1.0
    if cost_col:
        out["unit_cost"] = pd.to_numeric(frame[cost_col], errors="coerce")
    else:
        out["unit_cost"] = np.nan
    out["quantity"] = out["quantity"].astype(int)
    # Drop blank keys.
    mask = (out["card_id"].astype(str).str.len() > 0) | (out["name"].astype(str).str.len() > 0)
    return out.loc[mask].reset_index(drop=True)


def net_proceeds(price: float, *, fee_pct: float, ship_usd: float) -> float:
    """Cash after marketplace fee + flat shipping (seller side)."""
    p = float(price)
    if p <= 0:
        return 0.0
    fee = max(0.0, float(fee_pct)) / 100.0
    ship = max(0.0, float(ship_usd))
    return max(0.0, p * (1.0 - fee) - ship)


def desk_action(
    *,
    signal: str,
    expected_pct: float,
    conformal_ok: bool,
    net_edge_pct: float,
    band_pct: float = FORECAST_SIGNAL_BAND * 100.0,
) -> str:
    """Map board signal + fee-aware edge to dealer action."""
    if not conformal_ok:
        return ACTION_HOLD
    sig = str(signal or SIGNAL_HOLD).upper()
    if sig in {SIGNAL_SELL, "PRODAJ", "PRODAJ/ČEKAJ"} and net_edge_pct <= -abs(band_pct):
        return ACTION_LIST
    if sig in {SIGNAL_BUY, "KUPI"} and net_edge_pct >= abs(band_pct):
        return ACTION_BUY_MORE
    # Fee-aware override when board is HOLD but net edge is strong.
    if net_edge_pct >= max(8.0, abs(band_pct) * 2):
        return ACTION_BUY_MORE
    if net_edge_pct <= -max(8.0, abs(band_pct) * 2):
        return ACTION_LIST
    del expected_pct  # reserved for future sizing
    return ACTION_HOLD


def build_dealer_board(
    inventory: pd.DataFrame,
    market: pd.DataFrame,
    *,
    fee_pct: float = DEFAULT_SELL_FEE_PCT,
    ship_usd: float = DEFAULT_SHIP_USD,
) -> pd.DataFrame:
    """Join inventory to market quotes; compute net edge and actions."""
    if inventory is None or inventory.empty:
        return pd.DataFrame()
    if market is None or market.empty or "id" not in market.columns:
        raise ValueError("Market board is empty.")

    inv = inventory.copy()
    quotes = market.copy()
    quotes["id"] = quotes["id"].astype(str)
    quotes["_name_key"] = quotes.get("name", pd.Series(dtype=str)).astype(str).str.strip().str.lower()
    id_index = {str(i): idx for idx, i in enumerate(quotes["id"].tolist())}

    matched_rows: list[dict[str, Any]] = []
    unmatched = 0
    for row in inv.itertuples(index=False):
        card_id = str(getattr(row, "card_id", "") or "").strip()
        name = str(getattr(row, "name", "") or "").strip()
        qty = int(getattr(row, "quantity", 1) or 1)
        unit_cost = getattr(row, "unit_cost", np.nan)
        hit = None
        if card_id and card_id in id_index:
            hit = quotes.iloc[id_index[card_id]]
        elif name:
            key = name.lower()
            sub = quotes.loc[quotes["_name_key"] == key]
            if len(sub) == 1:
                hit = sub.iloc[0]
            elif len(sub) > 1:
                # Prefer highest price print if ambiguous.
                hit = sub.sort_values("price", ascending=False).iloc[0]
        if hit is None:
            unmatched += 1
            matched_rows.append(
                {
                    "card_id": card_id or None,
                    "name": name or None,
                    "quantity": qty,
                    "unit_cost": float(unit_cost) if pd.notna(unit_cost) else None,
                    "matched": False,
                    "spot": None,
                    "expected_change_pct": None,
                    "signal": SIGNAL_HOLD,
                    "conformal_ok": False,
                    "pred_lo_pct": None,
                    "pred_hi_pct": None,
                    "net_now": None,
                    "net_forecast": None,
                    "net_edge_pct": None,
                    "action": ACTION_HOLD,
                }
            )
            continue

        spot = float(pd.to_numeric(hit.get("price"), errors="coerce") or 0.0)
        exp = pd.to_numeric(hit.get("expected_change_pct"), errors="coerce")
        exp_pct = float(exp) if pd.notna(exp) else 0.0
        forecast_spot = spot * (1.0 + exp_pct / 100.0)
        net_now = net_proceeds(spot, fee_pct=fee_pct, ship_usd=ship_usd)
        net_fc = net_proceeds(forecast_spot, fee_pct=fee_pct, ship_usd=ship_usd)
        if net_now > 0:
            net_edge_pct = (net_fc - net_now) / net_now * 100.0
        else:
            net_edge_pct = exp_pct
        conf_ok = hit.get("confidence_ok", True)
        conf_ok = True if conf_ok is None or (isinstance(conf_ok, float) and pd.isna(conf_ok)) else bool(conf_ok)
        c_ok = hit.get("conformal_ok", True)
        c_ok = True if c_ok is None or (isinstance(c_ok, float) and pd.isna(c_ok)) else bool(c_ok)
        ok = bool(conf_ok and c_ok)
        signal = str(hit.get("signal") or SIGNAL_HOLD)
        action = desk_action(
            signal=signal,
            expected_pct=exp_pct,
            conformal_ok=ok,
            net_edge_pct=net_edge_pct,
        )
        matched_rows.append(
            {
                "card_id": str(hit.get("id")),
                "name": str(hit.get("name") or name or hit.get("id")),
                "set_name": str(hit.get("set_name") or ""),
                "quantity": qty,
                "unit_cost": float(unit_cost) if pd.notna(unit_cost) else None,
                "matched": True,
                "spot": spot,
                "expected_change_pct": exp_pct,
                "signal": signal,
                "conformal_ok": ok,
                "pred_lo_pct": float(hit["pred_lo_pct"])
                if "pred_lo_pct" in hit and pd.notna(hit.get("pred_lo_pct"))
                else None,
                "pred_hi_pct": float(hit["pred_hi_pct"])
                if "pred_hi_pct" in hit and pd.notna(hit.get("pred_hi_pct"))
                else None,
                "net_now": net_now,
                "net_forecast": net_fc,
                "net_edge_pct": net_edge_pct,
                "action": action,
                "inventory_value": spot * qty,
            }
        )

    board = pd.DataFrame(matched_rows)
    if board.empty:
        return board
    # Actionable conformal rows first, then |net edge|.
    board["_rank_action"] = board["action"].map(
        {ACTION_LIST: 0, ACTION_BUY_MORE: 1, ACTION_HOLD: 2}
    ).fillna(2)
    board["_rank_conf"] = (~board["conformal_ok"].fillna(False)).astype(int)
    board["_rank_edge"] = -board["net_edge_pct"].abs().fillna(0.0)
    board = board.sort_values(
        ["_rank_conf", "_rank_action", "_rank_edge"], kind="mergesort"
    ).drop(columns=["_rank_action", "_rank_conf", "_rank_edge"])
    board.attrs["unmatched"] = unmatched
    board.attrs["fee_pct"] = float(fee_pct)
    board.attrs["ship_usd"] = float(ship_usd)
    return board.reset_index(drop=True)

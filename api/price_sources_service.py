"""Multi-source price history for Soft Ink detail (DB + JustTCG NM + PSA 10)."""

from __future__ import annotations

import logging
from typing import Any

from api.catalog_service import load_board, load_card_history
from justtcg_client import justtcg_api_key, normalize_card_number

LOG = logging.getLogger("kestrel.api.price_sources")


def _points_from_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows or []:
        try:
            out.append(
                {
                    "date": str(row.get("date") or "")[:10],
                    "price": float(row["price"]),
                }
            )
        except (TypeError, ValueError, KeyError):
            continue
    out.sort(key=lambda p: p["date"])
    return out


def _resolve_tcp_from_board(card_id: str) -> tuple[str, str, str | None]:
    """Return (name, set_name, tcgplayer_id) best-effort from board/DB."""
    name = str(card_id)
    set_name = ""
    tcp: str | None = None
    board, _ = load_board()
    if board is not None and not board.empty:
        hits = board[board["id"].astype(str) == str(card_id)]
        if not hits.empty:
            row = hits.iloc[0]
            name = str(row.get("name") or card_id)
            set_name = str(row.get("set_name") or "")
            raw_tcp = row.get("tcgplayer_id") if hasattr(row, "get") else None
            if raw_tcp is not None and str(raw_tcp).strip() and str(raw_tcp).lower() != "nan":
                tcp = str(raw_tcp).strip()
    if tcp:
        return name, set_name, tcp
    try:
        from database import get_card

        card = get_card(str(card_id))
        if card is not None:
            name = str(card.name or name)
            set_name = str(getattr(card, "set_name", None) or set_name)
            if getattr(card, "tcgplayer_id", None):
                tcp = str(card.tcgplayer_id)
    except Exception as exc:
        LOG.info("get_card tcgplayer_id lookup failed: %s", exc)
    return name, set_name, tcp


def build_card_price_sources(card_id: str, *, limit: int = 180) -> dict[str, Any]:
    card_id = str(card_id).strip()
    market = _points_from_rows(load_card_history(card_id, limit=limit))
    name, set_name, tcp = _resolve_tcp_from_board(card_id)
    has_key = bool(justtcg_api_key())
    number = ""
    if "-" in card_id:
        number = normalize_card_number(card_id.rsplit("-", 1)[-1])

    justtcg: list[dict[str, Any]] = []
    justtcg_error: str | None = None
    justtcg_fallback = False
    psa10: list[dict[str, Any]] = []
    psa10_error: str | None = None
    psa10_stats: dict[str, Any] = {}

    if has_key:
        try:
            from justtcg_client import nm_history_for_card

            points, resolved = nm_history_for_card(
                tcgplayer_id=tcp,
                name=name,
                number=number or None,
                set_name=set_name or None,
            )
            if resolved:
                tcp = str(resolved)
            justtcg = _points_from_rows(points)
        except Exception as exc:
            justtcg_error = str(exc)[:180]
            LOG.info("nm_history_for_card failed for %s: %s", card_id, exc)

        if not justtcg and market:
            justtcg = list(market)
            justtcg_fallback = True

        try:
            from justtcg_client import psa10_history_for_card

            points, resolved, stats = psa10_history_for_card(
                tcgplayer_id=tcp,
                name=name,
                number=number or None,
                set_name=set_name or None,
            )
            if resolved:
                tcp = str(resolved)
            psa10 = _points_from_rows(points)
            psa10_stats = dict(stats or {})
        except Exception as exc:
            psa10_error = str(exc)[:180]
            LOG.info("psa10_history_for_card failed for %s: %s", card_id, exc)

    return {
        "card_id": card_id,
        "name": name,
        "set_name": set_name or None,
        "tcgplayer_id": tcp,
        "justtcg_configured": has_key,
        "tcgplayer": market,
        "justtcg": justtcg,
        "justtcg_fallback": justtcg_fallback,
        "justtcg_error": justtcg_error,
        "psa10": psa10,
        "psa10_error": psa10_error,
        "psa10_stats": {
            "has_history_series": bool(psa10_stats.get("has_history_series")),
            "period_key": psa10_stats.get("period_key"),
            "sales_count": psa10_stats.get("sales_count"),
        },
    }

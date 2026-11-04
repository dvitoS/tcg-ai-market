"""Watchlist alert digest for Soft Ink (no Streamlit session)."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from api.catalog_service import load_board
from api.demo_mode import demo_mode
from api.portfolio_service import list_watchlist
from services.alerts import WatchAlert, alert_body_text, collect_watchlist_alerts
from services.pro import is_pro_user

LOG = logging.getLogger("kestrel.api.alerts")


def _money(value: float) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$—"


def _watch_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["card_id", "name"])
    return pd.DataFrame(
        [
            {
                "card_id": str(row.get("card_id") or ""),
                "name": row.get("name"),
            }
            for row in rows
            if str(row.get("card_id") or "").strip()
        ]
    )


def collect_user_watchlist_alerts(
    *,
    user_id: str,
    threshold_pct: float = 5.0,
    sure_only: bool = False,
    access_token: str | None = None,
    dismissed: list[str] | None = None,
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Soft Ink alert digest payload for one authenticated user."""
    band = max(1.0, min(50.0, float(threshold_pct)))
    pro = bool(is_pro_user(user))
    # Sure-only is a Pro surface (matches Streamlit portfolio).
    effective_sure = bool(sure_only) if pro else False

    board, source = load_board()
    watch_rows = list_watchlist(user_id=user_id, access_token=access_token)
    watch = _watch_frame(watch_rows)
    dismissed_set = {str(x) for x in (dismissed or []) if str(x).strip()}

    if board is None or board.empty or watch.empty:
        return {
            "items": [],
            "threshold_pct": band,
            "sure_only": effective_sure,
            "sure_only_allowed": pro,
            "watch_count": int(len(watch_rows)),
            "demo": demo_mode(),
            "source": source,
        }

    try:
        alerts = collect_watchlist_alerts(
            board,
            watch,
            threshold_pct=band,
            dismissed=dismissed_set,
            sure_only=effective_sure,
        )
    except Exception as exc:
        LOG.warning("collect_watchlist_alerts failed: %s", exc)
        alerts = []

    items = [_alert_payload(alert) for alert in alerts]
    return {
        "items": items,
        "threshold_pct": band,
        "sure_only": effective_sure,
        "sure_only_allowed": pro,
        "watch_count": int(len(watch_rows)),
        "demo": demo_mode(),
        "source": source,
    }


def _alert_payload(alert: WatchAlert) -> dict[str, Any]:
    return {
        "card_id": alert.card_id,
        "name": alert.name,
        "expected_pct": float(alert.expected_pct),
        "price_change_pct": (
            float(alert.price_change_pct) if alert.price_change_pct is not None else None
        ),
        "signal": alert.signal or None,
        "price": float(alert.price),
        "reason": alert.reason,
        "conformal_ok": bool(alert.conformal_ok),
        "sure": bool(alert.sure),
        "body": alert_body_text(alert, money_fmt=_money),
    }

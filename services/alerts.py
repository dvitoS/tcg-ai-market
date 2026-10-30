"""In-app watchlist alerts (session-scoped, non-spammy)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
import streamlit as st

from i18n import signal_label, t

LOG = logging.getLogger("tcg.alerts")


@dataclass
class WatchAlert:
    card_id: str
    name: str
    expected_pct: float
    signal: str
    price: float


def _dismissed() -> set[str]:
    raw = st.session_state.setdefault("_watch_alert_dismissed", set())
    if not isinstance(raw, set):
        raw = set(raw)
        st.session_state["_watch_alert_dismissed"] = raw
    return raw


def dismiss_watch_alert(card_id: str) -> None:
    _dismissed().add(str(card_id))


def clear_watch_alert_dismissals() -> None:
    st.session_state["_watch_alert_dismissed"] = set()


def collect_watchlist_alerts(
    market: pd.DataFrame,
    watch: pd.DataFrame,
    *,
    threshold_pct: float = 5.0,
) -> list[WatchAlert]:
    """Cards on the watchlist whose AI expected move exceeds threshold."""
    if market.empty or watch.empty or "id" not in market.columns:
        return []
    dismissed = _dismissed()
    quotes = market.set_index("id", drop=False)
    out: list[WatchAlert] = []
    for row in watch.itertuples(index=False):
        card_id = str(row.card_id)
        if card_id in dismissed or card_id not in quotes.index:
            continue
        q = quotes.loc[card_id]
        if isinstance(q, pd.DataFrame):
            q = q.iloc[0]
        conf_ok = True
        if hasattr(q, "get"):
            conf_ok = q.get("confidence_ok", True)
        else:
            conf_ok = getattr(q, "confidence_ok", True)
        if conf_ok is not None and not (isinstance(conf_ok, float) and pd.isna(conf_ok)):
            if not bool(conf_ok):
                continue
        exp = q.get("expected_change_pct") if hasattr(q, "get") else getattr(q, "expected_change_pct", None)
        if exp is None or pd.isna(exp):
            continue
        expected = float(exp)
        if abs(expected) < float(threshold_pct):
            continue
        signal = str(q.get("signal") if hasattr(q, "get") else getattr(q, "signal", "") or "")
        price = float(q.get("price") if hasattr(q, "get") else getattr(q, "price", 0) or 0)
        name = str(
            q.get("name") if hasattr(q, "get") else getattr(q, "name", None) or getattr(row, "name", card_id)
        )
        out.append(
            WatchAlert(
                card_id=card_id,
                name=name,
                expected_pct=expected,
                signal=signal,
                price=price,
            )
        )
    out.sort(key=lambda a: abs(a.expected_pct), reverse=True)
    return out


def render_watchlist_alerts(alerts: list[WatchAlert], *, money_fmt) -> None:
    """Show dismissible banners for active watchlist alerts."""
    if not alerts:
        return
    for alert in alerts[:5]:
        tone = "success" if alert.expected_pct >= 0 else "warning"
        label = t(
            "alert_watch_body",
            name=alert.name,
            pct=alert.expected_pct,
            signal=signal_label(alert.signal) if alert.signal else "—",
            price=money_fmt(alert.price),
        )
        cols = st.columns([6, 1])
        with cols[0]:
            if tone == "success":
                st.success(label)
            else:
                st.warning(label)
        with cols[1]:
            if st.button(
                t("alert_dismiss"),
                key=f"dismiss_watch_{alert.card_id}",
                use_container_width=True,
            ):
                dismiss_watch_alert(alert.card_id)
                st.rerun()


def safe_collect_and_render_alerts(
    market: pd.DataFrame,
    *,
    user_id: str,
    threshold_pct: float,
    money_fmt,
) -> None:
    """Load watchlist + render alerts; log failures instead of silent pass."""
    if not user_id:
        return
    try:
        from database import load_watchlist

        watch_rows = load_watchlist(user_id=user_id)
        alerts = collect_watchlist_alerts(market, watch_rows, threshold_pct=threshold_pct)
        if alerts:
            st.caption(t("alert_watch_caption", pct=threshold_pct))
            render_watchlist_alerts(alerts, money_fmt=money_fmt)
    except Exception as exc:
        LOG.warning("watchlist alerts failed: %s", exc)
        st.caption(t("watchlist_alerts_error"))

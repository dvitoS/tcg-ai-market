"""In-app watchlist alerts (session-scoped, non-spammy)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st


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
        label = (
            f"Watchlist · {alert.name}: {alert.expected_pct:+.1f}% expected"
            f" ({alert.signal or '—'}) · {money_fmt(alert.price)}"
        )
        cols = st.columns([6, 1])
        with cols[0]:
            if tone == "success":
                st.success(label)
            else:
                st.warning(label)
        with cols[1]:
            if st.button("Dismiss", key=f"dismiss_watch_{alert.card_id}", use_container_width=True):
                dismiss_watch_alert(alert.card_id)
                st.rerun()

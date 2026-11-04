"""In-app watchlist alerts (session-scoped, non-spammy)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from trading_signals import SIGNAL_BUY, SIGNAL_SELL

LOG = logging.getLogger("tcg.alerts")

_ACTIONABLE = {SIGNAL_BUY, SIGNAL_SELL, "KUPI", "PRODAJ", "PRODAJ/ČEKAJ"}


@dataclass
class WatchAlert:
    card_id: str
    name: str
    expected_pct: float
    signal: str
    price: float
    reason: str = "ai"  # "ai" | "price" | "both"
    price_change_pct: float | None = None
    conformal_ok: bool = True
    sure: bool = False


def _streamlit():
    import streamlit as st

    return st


def _dismissed() -> set[str]:
    st = _streamlit()
    raw = st.session_state.setdefault("_watch_alert_dismissed", set())
    if not isinstance(raw, set):
        raw = set(raw)
        st.session_state["_watch_alert_dismissed"] = raw
    return raw


def dismiss_watch_alert(card_id: str) -> None:
    _dismissed().add(str(card_id))


def clear_watch_alert_dismissals() -> None:
    _streamlit().session_state["_watch_alert_dismissed"] = set()


def _cell(q, key: str, default=None):
    if hasattr(q, "get"):
        return q.get(key, default)
    return getattr(q, key, default)


def _truthy(raw, default: bool = True) -> bool:
    if raw is None:
        return default
    if isinstance(raw, float) and pd.isna(raw):
        return default
    return bool(raw)


def is_sure_alert(
    *,
    signal: str,
    conformal_ok: bool,
    confidence_ok: bool,
    reason: str,
) -> bool:
    """Actionable AI signal with conformal + confidence gates (no price-only noise)."""
    if not confidence_ok or not conformal_ok:
        return False
    if reason == "price":
        return False
    return str(signal or "").upper() in _ACTIONABLE


def collect_watchlist_alerts(
    market: pd.DataFrame,
    watch: pd.DataFrame,
    *,
    threshold_pct: float = 5.0,
    dismissed: set[str] | None = None,
    sure_only: bool = False,
) -> list[WatchAlert]:
    """Watchlist cards where |AI ROI| or |7d price move| ≥ threshold.

    When ``sure_only`` is True, keep only conformal BUY/SELL (or both) hits —
    drop uncertain intervals and pure 7d price moves.
    """
    if market.empty or watch.empty or "id" not in market.columns:
        return []
    if dismissed is None:
        try:
            dismissed = _dismissed()
        except Exception:
            dismissed = set()
    quotes = market.set_index("id", drop=False)
    band = float(threshold_pct)
    out: list[WatchAlert] = []
    for row in watch.itertuples(index=False):
        card_id = str(row.card_id)
        if card_id in dismissed or card_id not in quotes.index:
            continue
        q = quotes.loc[card_id]
        if isinstance(q, pd.DataFrame):
            q = q.iloc[0]
        conf_ok = _truthy(_cell(q, "confidence_ok", True), True)
        c_ok = _truthy(_cell(q, "conformal_ok", True), True)
        if not conf_ok:
            continue

        exp_raw = _cell(q, "expected_change_pct")
        price_raw = _cell(q, "price_change_7d_pct")
        expected = (
            float(exp_raw)
            if exp_raw is not None and not (isinstance(exp_raw, float) and pd.isna(exp_raw))
            else None
        )
        price_chg = (
            float(price_raw)
            if price_raw is not None and not (isinstance(price_raw, float) and pd.isna(price_raw))
            else None
        )
        ai_hit = expected is not None and abs(expected) >= band
        price_hit = price_chg is not None and abs(price_chg) >= band
        if not ai_hit and not price_hit:
            continue
        if ai_hit and price_hit:
            reason = "both"
        elif price_hit:
            reason = "price"
        else:
            reason = "ai"
        signal = str(_cell(q, "signal", "") or "")
        sure = is_sure_alert(
            signal=signal,
            conformal_ok=c_ok,
            confidence_ok=conf_ok,
            reason=reason,
        )
        if sure_only and not sure:
            continue
        price = float(_cell(q, "price", 0) or 0)
        name = str(_cell(q, "name") or getattr(row, "name", card_id) or card_id)
        out.append(
            WatchAlert(
                card_id=card_id,
                name=name,
                expected_pct=float(expected if expected is not None else 0.0),
                signal=signal,
                price=price,
                reason=reason,
                price_change_pct=price_chg,
                conformal_ok=c_ok,
                sure=sure,
            )
        )
    out.sort(
        key=lambda a: (
            0 if a.sure else 1,
            -max(
                abs(a.expected_pct),
                abs(a.price_change_pct) if a.price_change_pct is not None else 0.0,
            ),
        ),
    )
    return out


def _alert_body(alert: WatchAlert, *, money_fmt) -> str:
    from i18n import signal_label, t

    if alert.reason == "price" and alert.price_change_pct is not None:
        return t(
            "alert_watch_body_price",
            name=alert.name,
            pct=alert.price_change_pct,
            price=money_fmt(alert.price),
        )
    if alert.reason == "both" and alert.price_change_pct is not None:
        return t(
            "alert_watch_body_both",
            name=alert.name,
            ai_pct=alert.expected_pct,
            price_pct=alert.price_change_pct,
            signal=signal_label(alert.signal) if alert.signal else "—",
            price=money_fmt(alert.price),
        )
    return t(
        "alert_watch_body",
        name=alert.name,
        pct=alert.expected_pct,
        signal=signal_label(alert.signal) if alert.signal else "—",
        price=money_fmt(alert.price),
    )


def alert_body_text(alert: WatchAlert, *, money_fmt) -> str:
    """Public helper for Soft Ink / API digest lines (no Streamlit)."""
    return _alert_body(alert, money_fmt=money_fmt)


def render_watchlist_alerts(alerts: list[WatchAlert], *, money_fmt) -> None:
    """Show dismissible banners for active watchlist alerts."""
    st = _streamlit()
    from i18n import t

    if not alerts:
        return
    for alert in alerts[:5]:
        tone = "success" if alert.expected_pct >= 0 or (alert.price_change_pct or 0) >= 0 else "warning"
        if alert.reason == "price" and alert.price_change_pct is not None:
            tone = "success" if alert.price_change_pct >= 0 else "warning"
        label = _alert_body(alert, money_fmt=money_fmt)
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


def render_watchlist_digest(
    alerts: list[WatchAlert],
    *,
    threshold_pct: float,
    money_fmt,
    sure_only: bool = False,
) -> None:
    """In-app digest panel (portfolio) — denser than top banners."""
    st = _streamlit()
    from i18n import t

    if not alerts:
        empty_key = "alert_digest_empty_sure" if sure_only else "alert_digest_empty"
        st.caption(t(empty_key, pct=threshold_pct))
        return
    cap_key = "alert_watch_caption_sure" if sure_only else "alert_watch_caption"
    st.caption(t(cap_key, pct=threshold_pct))
    lines = []
    for alert in alerts[:15]:
        prefix = "✓ " if alert.sure else ""
        lines.append(prefix + _alert_body(alert, money_fmt=money_fmt))
    st.markdown("\n\n".join(f"- {line}" for line in lines))
    if len(alerts) > 15:
        st.caption(t("alert_digest_more", n=len(alerts) - 15))


def safe_collect_and_render_alerts(
    market: pd.DataFrame,
    *,
    user_id: str,
    threshold_pct: float,
    money_fmt,
    sure_only: bool = True,
) -> None:
    """Load watchlist + render alerts; log failures instead of silent pass."""
    st = _streamlit()
    from i18n import t

    if not user_id:
        return
    try:
        from database import load_watchlist

        watch_rows = load_watchlist(user_id=user_id)
        alerts = collect_watchlist_alerts(
            market,
            watch_rows,
            threshold_pct=threshold_pct,
            sure_only=sure_only,
        )
        if alerts:
            cap_key = "alert_watch_caption_sure" if sure_only else "alert_watch_caption"
            st.caption(t(cap_key, pct=threshold_pct))
            render_watchlist_alerts(alerts, money_fmt=money_fmt)
    except Exception as exc:
        LOG.warning("watchlist alerts failed: %s", exc)
        st.caption(t("watchlist_alerts_error"))

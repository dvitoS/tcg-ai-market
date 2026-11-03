"""Optional SMTP digests for watchlist AI alerts (nightly)."""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

import pandas as pd

from config import _secret
from services.alerts import WatchAlert, collect_watchlist_alerts

LOG = logging.getLogger("tcg.email_alerts")


def _clean(name: str) -> str:
    return str(_secret(name) or os.getenv(name, "") or "").strip()


def smtp_configured() -> bool:
    return bool(_clean("SMTP_HOST") and _clean("SMTP_FROM") and _clean("SMTP_USER"))


def default_threshold_pct() -> float:
    raw = _clean("ALERT_THRESHOLD_PCT") or "5"
    try:
        return float(raw)
    except ValueError:
        return 5.0


def default_sure_only() -> bool:
    """Nightly digests default to sure-only (conformal BUY/SELL)."""
    raw = (_clean("ALERT_SURE_ONLY") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def format_digest(
    alerts: list[WatchAlert],
    *,
    threshold_pct: float,
    sure_only: bool = False,
) -> str:
    mode = (
        f"sure-only conformal BUY/SELL · |AI ROI| ≥ {threshold_pct:g}%"
        if sure_only
        else f"|AI ROI| or |7d price| ≥ {threshold_pct:g}%"
    )
    lines = [
        f"Kestrel — watchlist alerts ({mode})",
        "",
    ]
    for alert in alerts[:25]:
        mark = "✓" if alert.sure else "•"
        bits = [f"{mark} {alert.name} ({alert.card_id})"]
        if alert.reason in {"ai", "both"}:
            bits.append(f"AI {alert.expected_pct:+.1f}%")
        if alert.price_change_pct is not None and alert.reason in {"price", "both"}:
            bits.append(f"7d price {alert.price_change_pct:+.1f}%")
        bits.append(f"signal={alert.signal or '—'}")
        bits.append(f"price={alert.price:.4f}")
        lines.append(" · ".join(bits))
    if len(alerts) > 25:
        lines.append(f"… and {len(alerts) - 25} more")
    lines.append("")
    lines.append("Open the Streamlit app → Portfolio for the in-app digest.")
    return "\n".join(lines)


def send_smtp_email(*, to_addr: str, subject: str, body: str) -> bool:
    host = _clean("SMTP_HOST")
    port_raw = _clean("SMTP_PORT") or "587"
    user = _clean("SMTP_USER")
    password = _clean("SMTP_PASSWORD")
    from_addr = _clean("SMTP_FROM")
    if not (host and from_addr and to_addr and user):
        return False
    try:
        port = int(port_raw)
    except ValueError:
        port = 587

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            if port != 25:
                server.starttls(context=context)
                server.ehlo()
            if password:
                server.login(user, password)
            server.send_message(msg)
        return True
    except Exception as exc:
        LOG.warning("SMTP send to %s failed: %s", to_addr, exc)
        return False


def _email_for_user(user_id: str) -> str | None:
    """Resolve auth email via service-role admin API when available."""
    uid = str(user_id or "").strip()
    if not uid:
        return None
    try:
        from database import get_supabase

        client = get_supabase()
        response = client.auth.admin.get_user_by_id(uid)
        user = getattr(response, "user", None) or response
        email = getattr(user, "email", None)
        if email is None and isinstance(user, dict):
            email = user.get("email")
        email = str(email or "").strip()
        return email or None
    except Exception as exc:
        LOG.debug("admin get_user_by_id(%s) failed: %s", uid, exc)
        return None


def send_watchlist_digests(
    market: pd.DataFrame,
    *,
    threshold_pct: float | None = None,
    sure_only: bool | None = None,
) -> dict[str, Any]:
    """Email each watchlist owner (and optional ALERT_EMAIL_TO) a digest.

    No-op when SMTP is not configured. Never raises for partial user failures.
    Defaults to sure-only (conformal BUY/SELL) unless ALERT_SURE_ONLY=0.
    """
    stats = {"users": 0, "sent": 0, "skipped": 0, "alerts": 0, "sure_only": False}
    if not smtp_configured():
        LOG.info("SMTP not configured — skipping watchlist email digests")
        return stats
    if market is None or market.empty:
        return stats

    threshold = float(threshold_pct if threshold_pct is not None else default_threshold_pct())
    use_sure = bool(default_sure_only() if sure_only is None else sure_only)
    stats["sure_only"] = use_sure
    try:
        from database import load_all_watchlists

        watch = load_all_watchlists()
    except Exception as exc:
        LOG.warning("load_all_watchlists failed: %s", exc)
        return stats
    if watch.empty or "user_id" not in watch.columns:
        return stats

    fallback_to = _clean("ALERT_EMAIL_TO")
    for user_id, group in watch.groupby(watch["user_id"].astype(str)):
        stats["users"] += 1
        alerts = collect_watchlist_alerts(
            market,
            group,
            threshold_pct=threshold,
            dismissed=set(),
            sure_only=use_sure,
        )
        if not alerts:
            stats["skipped"] += 1
            continue
        stats["alerts"] += len(alerts)
        to_addr = _email_for_user(str(user_id)) or fallback_to
        if not to_addr:
            LOG.warning("No email for user_id=%s — skip digest", user_id)
            stats["skipped"] += 1
            continue
        body = format_digest(alerts, threshold_pct=threshold, sure_only=use_sure)
        kind = "sure" if use_sure else "watchlist"
        subject = f"[Kestrel] {len(alerts)} {kind} alert(s)"
        if send_smtp_email(to_addr=to_addr, subject=subject, body=body):
            stats["sent"] += 1
        else:
            stats["skipped"] += 1
    LOG.info("watchlist digests: %s", stats)
    return stats

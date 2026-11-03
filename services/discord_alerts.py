"""Optional Discord webhook for sure-only watchlist digests (nightly)."""

from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd
import requests

from config import _secret
from services.alerts import WatchAlert, collect_watchlist_alerts
from services.email_alerts import default_sure_only, default_threshold_pct
from trading_signals import SIGNAL_BUY, SIGNAL_SELL

LOG = logging.getLogger("tcg.discord_alerts")

_MAX_EMBEDS = 10
_MAX_FIELDS = 25


def _clean(name: str) -> str:
    return str(_secret(name) or os.getenv(name, "") or "").strip()


def discord_configured() -> bool:
    url = _clean("DISCORD_WEBHOOK_URL")
    return url.startswith("https://discord.com/api/webhooks/") or url.startswith(
        "https://discordapp.com/api/webhooks/"
    )


def webhook_url() -> str | None:
    if not discord_configured():
        return None
    return _clean("DISCORD_WEBHOOK_URL")


def _tone(signal: str) -> int:
    sig = str(signal or "").upper()
    if sig in {SIGNAL_BUY, "KUPI"}:
        return 0x22C55E  # green
    if sig in {SIGNAL_SELL, "PRODAJ", "PRODAJ/ČEKAJ"}:
        return 0xF59E0B  # amber
    return 0x64748B


def build_discord_payload(
    alerts: list[WatchAlert],
    *,
    threshold_pct: float,
    sure_only: bool = True,
) -> dict[str, Any]:
    """Discord webhook JSON: content + embeds (capped)."""
    mode = "sure-only conformal" if sure_only else "watchlist"
    content = f"**Kestrel** · {len(alerts)} {mode} alert(s) · |AI ROI| ≥ {threshold_pct:g}%"
    embeds: list[dict[str, Any]] = []
    # Pack alerts into embeds (≈8 fields each → stay under Discord limits).
    chunk: list[WatchAlert] = []
    for alert in alerts[:40]:
        chunk.append(alert)
        if len(chunk) >= 8:
            embeds.append(_embed_from_chunk(chunk, threshold_pct=threshold_pct))
            chunk = []
            if len(embeds) >= _MAX_EMBEDS:
                break
    if chunk and len(embeds) < _MAX_EMBEDS:
        embeds.append(_embed_from_chunk(chunk, threshold_pct=threshold_pct))
    payload: dict[str, Any] = {"content": content[:2000]}
    if embeds:
        payload["embeds"] = embeds
    return payload


def _embed_from_chunk(
    chunk: list[WatchAlert],
    *,
    threshold_pct: float,
) -> dict[str, Any]:
    del threshold_pct  # reserved for footer copy
    fields = []
    for alert in chunk[:_MAX_FIELDS]:
        bits = [f"AI {alert.expected_pct:+.1f}%", f"`{alert.signal or '—'}`"]
        if alert.price_change_pct is not None and alert.reason in {"price", "both"}:
            bits.append(f"7d {alert.price_change_pct:+.1f}%")
        bits.append(f"${alert.price:.2f}")
        fields.append(
            {
                "name": f"{alert.name}"[:256],
                "value": f"`{alert.card_id}` · " + " · ".join(bits),
                "inline": False,
            }
        )
    color = _tone(chunk[0].signal) if chunk else 0x64748B
    return {
        "title": "Watchlist · actionable",
        "color": color,
        "fields": fields,
    }


def post_webhook(payload: dict[str, Any], *, url: str | None = None) -> bool:
    target = (url or webhook_url() or "").strip()
    if not target:
        return False
    try:
        resp = requests.post(target, json=payload, timeout=20)
        if resp.status_code >= 400:
            LOG.warning(
                "Discord webhook HTTP %s: %s",
                resp.status_code,
                (resp.text or "")[:200],
            )
            return False
        return True
    except Exception as exc:
        LOG.warning("Discord webhook failed: %s", exc)
        return False


def collect_aggregated_sure_alerts(
    market: pd.DataFrame,
    *,
    threshold_pct: float | None = None,
    sure_only: bool = True,
) -> list[WatchAlert]:
    """Union of sure alerts across all watchlists, deduped by card_id (strongest |AI|)."""
    if market is None or market.empty:
        return []
    threshold = float(threshold_pct if threshold_pct is not None else default_threshold_pct())
    try:
        from database import load_all_watchlists

        watch = load_all_watchlists()
    except Exception as exc:
        LOG.warning("load_all_watchlists failed: %s", exc)
        return []
    if watch.empty:
        return []

    by_id: dict[str, WatchAlert] = {}
    if "user_id" in watch.columns:
        groups = watch.groupby(watch["user_id"].astype(str))
    else:
        groups = [("all", watch)]
    for _uid, group in groups:
        alerts = collect_watchlist_alerts(
            market,
            group,
            threshold_pct=threshold,
            dismissed=set(),
            sure_only=sure_only,
        )
        for alert in alerts:
            prev = by_id.get(alert.card_id)
            if prev is None or abs(alert.expected_pct) > abs(prev.expected_pct):
                by_id[alert.card_id] = alert
    out = list(by_id.values())
    out.sort(key=lambda a: abs(a.expected_pct), reverse=True)
    return out


def send_sure_discord_digest(
    market: pd.DataFrame,
    *,
    threshold_pct: float | None = None,
    sure_only: bool | None = None,
) -> dict[str, Any]:
    """Post one channel digest of sure-only alerts. No-op without webhook."""
    stats = {"sent": 0, "skipped": 0, "alerts": 0}
    if not discord_configured():
        LOG.info("Discord webhook not configured — skipping")
        return stats
    use_sure = bool(default_sure_only() if sure_only is None else sure_only)
    threshold = float(threshold_pct if threshold_pct is not None else default_threshold_pct())
    alerts = collect_aggregated_sure_alerts(
        market, threshold_pct=threshold, sure_only=use_sure
    )
    stats["alerts"] = len(alerts)
    if not alerts:
        stats["skipped"] = 1
        LOG.info("Discord digest: no alerts to post")
        return stats
    payload = build_discord_payload(
        alerts, threshold_pct=threshold, sure_only=use_sure
    )
    if post_webhook(payload):
        stats["sent"] = 1
    else:
        stats["skipped"] = 1
    LOG.info("Discord digest: %s", stats)
    return stats

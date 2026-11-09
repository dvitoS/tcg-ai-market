"""G3 spend-unlock trust metrics (refund / cancel citing wrong prices).

Soft-launch: Creem rarely sends structured refund reasons, so we combine:
- cancel/refund webhook outcomes + free-text reason classification
- wrong-spot report volume vs entitled Pro users

Gate target (ROADMAP): <2% of cancels/refunds cite wrong prices.
"""

from __future__ import annotations

import re
import threading
import time
from collections import Counter
from typing import Any

_LOCK = threading.Lock()
_STARTED_AT = time.time()
_CANCEL_REASONS: Counter[str] = Counter()
_WRONG_PRICE_HITS = 0
_REFUND_EVENTS = 0
_CANCEL_EVENTS = 0

_WRONG_PRICE_RE = re.compile(
    r"wrong\s*pric|bad\s*pric|incorrect\s*pric|inflat|overpric|"
    r"spot\s+(?:is\s+)?(?:wrong|off|bad)|"
    r"price\s+(?:is\s+)?(?:wrong|off|bad)|"
    r"bad\s+spots?|"
    r"krivi?\s+spot|kriva?\s+cijen|pogresn|pogrešn",
    re.IGNORECASE,
)


def looks_like_wrong_price(reason: str | None) -> bool:
    text = str(reason or "").strip()
    if not text:
        return False
    return bool(_WRONG_PRICE_RE.search(text))


def _bucket_reason(reason: str | None) -> str:
    text = str(reason or "").strip()
    if not text:
        return "(none)"
    if looks_like_wrong_price(text):
        return "wrong_price"
    # Keep short free-text buckets readable in ops UI.
    return text[:80].lower()


def record_cancel_or_refund(
    *,
    kind: str,
    reason: str | None = None,
    event_type: str | None = None,
) -> None:
    """Record a cancel/refund webhook for the G3 trust gate."""
    global _WRONG_PRICE_HITS, _REFUND_EVENTS, _CANCEL_EVENTS
    bucket = _bucket_reason(reason)
    hit = bucket == "wrong_price"
    with _LOCK:
        if kind == "refund":
            _REFUND_EVENTS += 1
        else:
            _CANCEL_EVENTS += 1
        _CANCEL_REASONS[bucket] += 1
        if hit:
            _WRONG_PRICE_HITS += 1
        if event_type:
            _CANCEL_REASONS[f"event:{event_type}"] += 1


def extract_cancel_reason(obj: dict[str, Any] | None) -> str | None:
    """Best-effort cancel/refund reason from a Creem-like payload."""
    data = obj if isinstance(obj, dict) else {}
    candidates: list[Any] = [
        data.get("cancellation_reason"),
        data.get("cancel_reason"),
        data.get("reason"),
        data.get("refund_reason"),
    ]
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    candidates.extend(
        [
            meta.get("cancellation_reason"),
            meta.get("cancel_reason"),
            meta.get("reason"),
            meta.get("refund_reason"),
            meta.get("note"),
        ]
    )
    for raw in candidates:
        text = str(raw or "").strip()
        if text:
            return text[:240]
    return None


def g3_trust_snapshot(
    *,
    entitled: int = 0,
    canceled: int = 0,
    spot_reports_open: int = 0,
    spot_reports_total: int = 0,
) -> dict[str, Any]:
    """Compose the ops-facing G3 trust strip."""
    with _LOCK:
        reasons = dict(_CANCEL_REASONS)
        wrong_hits = int(_WRONG_PRICE_HITS)
        refunds = int(_REFUND_EVENTS)
        cancels = int(_CANCEL_EVENTS)
        uptime_s = round(time.time() - _STARTED_AT, 1)

    cited = cancels + refunds
    wrong_price_pct = (
        round(100.0 * wrong_hits / cited, 2) if cited > 0 else None
    )
    # Soft proxy before refund volume exists: open reports per 100 entitled.
    reports_per_100 = (
        round(100.0 * spot_reports_open / entitled, 2) if entitled > 0 else None
    )
    gate_ok = True
    if wrong_price_pct is not None and wrong_price_pct >= 2.0:
        gate_ok = False
    return {
        "cancel_events": cancels,
        "refund_events": refunds,
        "cited_total": cited,
        "wrong_price_hits": wrong_hits,
        "wrong_price_pct": wrong_price_pct,
        "reason_buckets": reasons,
        "entitled": int(entitled),
        "canceled_entitlements": int(canceled),
        "spot_reports_open": int(spot_reports_open),
        "spot_reports_total": int(spot_reports_total),
        "spot_reports_per_100_entitled": reports_per_100,
        "gate_target_pct": 2.0,
        "gate_ok": gate_ok,
        "uptime_s": uptime_s,
    }


def reset_g3_trust_for_tests() -> None:
    global _WRONG_PRICE_HITS, _REFUND_EVENTS, _CANCEL_EVENTS, _STARTED_AT
    with _LOCK:
        _CANCEL_REASONS.clear()
        _WRONG_PRICE_HITS = 0
        _REFUND_EVENTS = 0
        _CANCEL_EVENTS = 0
        _STARTED_AT = time.time()

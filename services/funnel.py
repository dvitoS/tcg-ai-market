"""Soft-launch funnel counters (landing → DOTD → Pro → Radar/Trade).

In-process ring + counts — enough for ops during soft launch without a
third-party analytics vendor. Events are anonymous (session id only).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter, deque
from typing import Any

LOG = logging.getLogger("tcg.funnel")

# Keep the allowlist tight so random noise cannot inflate the funnel.
ALLOWED_EVENTS = frozenset(
    {
        "landing_view",
        "landing_cta_dotd",
        "landing_cta_pro",
        "dotd_cta",
        "dotd_card_open",
        "pro_view",
        "pro_checkout_click",
        "pro_open_radar",
        "pro_open_trade",
        "radar_activate",
        "trade_activate",
        "share_copy",
        "share_png",
    }
)

_LOCK = threading.Lock()
_COUNTS: Counter[str] = Counter()
_RECENT: deque[dict[str, Any]] = deque(maxlen=200)
_STARTED_AT = time.time()


def record_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate and record a batch of funnel events. Returns accept stats."""
    accepted = 0
    rejected = 0
    with _LOCK:
        for raw in events:
            name = str((raw or {}).get("event") or "").strip()
            if name not in ALLOWED_EVENTS:
                rejected += 1
                continue
            session = str((raw or {}).get("session") or "")[:64]
            props = (raw or {}).get("props")
            if props is not None and not isinstance(props, dict):
                props = None
            entry = {
                "event": name,
                "session": session or None,
                "props": props,
                "ts": time.time(),
            }
            _COUNTS[name] += 1
            _RECENT.appendleft(entry)
            accepted += 1
            LOG.info(
                "funnel event=%s session=%s props=%s",
                name,
                session or "-",
                props or {},
            )
    return {"accepted": accepted, "rejected": rejected}


def funnel_summary() -> dict[str, Any]:
    with _LOCK:
        counts = dict(_COUNTS)
        recent = list(_RECENT)[:40]
        total = int(sum(_COUNTS.values()))
    return {
        "counts": counts,
        "total": total,
        "recent": recent,
        "uptime_s": round(time.time() - _STARTED_AT, 1),
        "allowed_events": sorted(ALLOWED_EVENTS),
    }


def reset_funnel_for_tests() -> None:
    with _LOCK:
        _COUNTS.clear()
        _RECENT.clear()

"""Process-local Creem webhook outcome counters for trial hygiene (M4.3)."""

from __future__ import annotations

import threading
import time
from collections import Counter
from typing import Any

_LOCK = threading.Lock()
_OUTCOMES: Counter[str] = Counter()
_STARTED_AT = time.time()


def record_webhook_outcome(*, action: str, status: str | None, event_type: str) -> None:
    key = f"{action}:{status or 'n/a'}:{event_type or 'unknown'}"
    with _LOCK:
        _OUTCOMES[key] += 1
        _OUTCOMES["total"] += 1


def webhook_outcome_counts() -> dict[str, Any]:
    with _LOCK:
        return {
            "counts": dict(_OUTCOMES),
            "uptime_s": round(time.time() - _STARTED_AT, 1),
        }


def reset_webhook_outcomes_for_tests() -> None:
    with _LOCK:
        _OUTCOMES.clear()

"""Wrong-spot user reports → ops queue (M4.4).

Process-local ring buffer — enough for soft-launch SLA without a new table.
Ops resolve via heal + mark_resolved; SLA targets documented in
``docs/WRONG_SPOT_SLA.md``.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from typing import Any, Literal

LOG_STATUS = Literal["open", "acked", "resolved", "dismissed"]

_LOCK = threading.Lock()
_REPORTS: deque[dict[str, Any]] = deque(maxlen=200)
_STARTED_AT = time.time()

# Soft-launch SLA (hours). Documented in WRONG_SPOT_SLA.md.
ACK_SLA_HOURS = 24
HEAL_SLA_HOURS = 48


def submit_spot_report(
    *,
    card_id: str,
    note: str | None = None,
    spot: float | None = None,
    session: str | None = None,
) -> dict[str, Any]:
    cid = str(card_id or "").strip()
    if not cid:
        raise ValueError("card_id required")
    entry = {
        "id": str(uuid.uuid4()),
        "card_id": cid[:80],
        "note": (str(note or "").strip()[:280] or None),
        "spot": float(spot) if spot is not None and float(spot) == float(spot) else None,
        "session": (str(session or "").strip()[:64] or None),
        "status": "open",
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    with _LOCK:
        _REPORTS.appendleft(entry)
        return dict(entry)


def list_spot_reports(
    *,
    status: str | None = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    with _LOCK:
        rows = list(_REPORTS)
    if status:
        want = str(status).strip().lower()
        rows = [r for r in rows if str(r.get("status")) == want]
    return [dict(r) for r in rows[: max(1, min(100, int(limit)))]]


def set_report_status(report_id: str, status: LOG_STATUS) -> dict[str, Any] | None:
    rid = str(report_id or "").strip()
    with _LOCK:
        for row in _REPORTS:
            if str(row.get("id")) == rid:
                row["status"] = status
                row["updated_at"] = time.time()
                return dict(row)
    return None


def open_report_card_ids(limit: int = 50) -> list[str]:
    open_rows = list_spot_reports(status="open", limit=limit)
    acked = list_spot_reports(status="acked", limit=limit)
    ids: list[str] = []
    seen: set[str] = set()
    for row in open_rows + acked:
        cid = str(row.get("card_id") or "")
        if cid and cid not in seen:
            seen.add(cid)
            ids.append(cid)
    return ids[:limit]


def spot_report_summary() -> dict[str, Any]:
    with _LOCK:
        rows = list(_REPORTS)
    counts = {"open": 0, "acked": 0, "resolved": 0, "dismissed": 0}
    oldest_open_age_h: float | None = None
    now = time.time()
    for row in rows:
        st = str(row.get("status") or "open")
        counts[st] = counts.get(st, 0) + 1
        if st in {"open", "acked"}:
            age_h = (now - float(row.get("created_at") or now)) / 3600.0
            if oldest_open_age_h is None or age_h > oldest_open_age_h:
                oldest_open_age_h = age_h
    overdue_ack = 0
    overdue_heal = 0
    for row in rows:
        if str(row.get("status")) not in {"open", "acked"}:
            continue
        age_h = (now - float(row.get("created_at") or now)) / 3600.0
        if str(row.get("status")) == "open" and age_h > ACK_SLA_HOURS:
            overdue_ack += 1
        if age_h > HEAL_SLA_HOURS:
            overdue_heal += 1
    return {
        "counts": counts,
        "open_total": int(counts.get("open", 0) + counts.get("acked", 0)),
        "oldest_open_age_h": (
            round(oldest_open_age_h, 2) if oldest_open_age_h is not None else None
        ),
        "overdue_ack": overdue_ack,
        "overdue_heal": overdue_heal,
        "ack_sla_hours": ACK_SLA_HOURS,
        "heal_sla_hours": HEAL_SLA_HOURS,
        "recent": [dict(r) for r in rows[:20]],
        "uptime_s": round(now - _STARTED_AT, 1),
    }


def reset_spot_reports_for_tests() -> None:
    with _LOCK:
        _REPORTS.clear()

"""Wrong-spot user reports → ops queue (M4.4).

Queue persists across API restarts (local JSON + optional Supabase
``model_artifacts``), same pattern as funnel / g3_trust. Soft-launch SLA
targets documented in ``docs/WRONG_SPOT_SLA.md``.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Literal

from config import PROJECT_ROOT

LOG = logging.getLogger("tcg.spot_reports")

SPOT_REPORTS_ARTIFACT_ID = "spot_reports_queue"
LOCAL_PATH = PROJECT_ROOT / ".data" / "spot_reports.json"
MAX_REPORTS = 200

LOG_STATUS = Literal["open", "acked", "resolved", "dismissed"]
_VALID_STATUS = frozenset({"open", "acked", "resolved", "dismissed"})

_LOCK = threading.Lock()
_REPORTS: deque[dict[str, Any]] = deque(maxlen=MAX_REPORTS)
_STARTED_AT = time.time()
_HYDRATED = False
_PERSIST_SOURCE = "memory"

# Soft-launch SLA (hours). Documented in WRONG_SPOT_SLA.md.
ACK_SLA_HOURS = 24
HEAL_SLA_HOURS = 48


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_row(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    cid = str(raw.get("card_id") or "").strip()
    rid = str(raw.get("id") or "").strip()
    if not cid or not rid:
        return None
    status = str(raw.get("status") or "open").strip().lower()
    if status not in _VALID_STATUS:
        status = "open"
    try:
        created = float(raw.get("created_at") or time.time())
    except (TypeError, ValueError):
        created = time.time()
    try:
        updated = float(raw.get("updated_at") or created)
    except (TypeError, ValueError):
        updated = created
    spot_raw = raw.get("spot")
    spot: float | None
    try:
        spot = float(spot_raw) if spot_raw is not None else None
        if spot is not None and spot != spot:
            spot = None
    except (TypeError, ValueError):
        spot = None
    return {
        "id": rid[:64],
        "card_id": cid[:80],
        "note": (str(raw.get("note") or "").strip()[:280] or None),
        "spot": spot,
        "session": (str(raw.get("session") or "").strip()[:64] or None),
        "status": status,
        "created_at": created,
        "updated_at": updated,
    }


def _snapshot() -> dict[str, Any]:
    return {
        "reports": list(_REPORTS),
        "updated_at": _utc_now(),
        "total": len(_REPORTS),
    }


def _apply_snapshot(payload: dict[str, Any] | None) -> bool:
    if not payload or not isinstance(payload, dict):
        return False
    rows_raw = payload.get("reports")
    if not isinstance(rows_raw, list):
        return False
    cleaned: list[dict[str, Any]] = []
    for item in rows_raw[:MAX_REPORTS]:
        row = _normalize_row(item if isinstance(item, dict) else None)
        if row:
            cleaned.append(row)
    # Newest first (same as appendleft order).
    cleaned.sort(key=lambda r: float(r.get("created_at") or 0), reverse=True)
    _REPORTS.clear()
    _REPORTS.extend(cleaned)
    return True


def _write_local(payload: dict[str, Any]) -> None:
    LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LOCAL_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(LOCAL_PATH)


def _read_local() -> dict[str, Any] | None:
    if not LOCAL_PATH.is_file():
        return None
    try:
        return dict(json.loads(LOCAL_PATH.read_text(encoding="utf-8")))
    except Exception as exc:
        LOG.warning("local spot_reports read failed: %s", exc)
        return None


def _save_supabase(payload: dict[str, Any]) -> bool:
    try:
        from database import get_supabase

        client = get_supabase()
        row = {
            "id": SPOT_REPORTS_ARTIFACT_ID,
            "algo": "spot_reports",
            "blob_b64": "",
            "metrics": payload,
            "feature_columns": [],
            "trained_at": payload.get("updated_at") or _utc_now(),
        }
        client.table("model_artifacts").upsert(row, on_conflict="id").execute()
        return True
    except Exception as exc:
        LOG.warning("supabase spot_reports save failed: %s", exc)
        return False


def _load_supabase() -> dict[str, Any] | None:
    try:
        from database import get_supabase

        client = get_supabase()
        response = (
            client.table("model_artifacts")
            .select("metrics")
            .eq("id", SPOT_REPORTS_ARTIFACT_ID)
            .limit(1)
            .execute()
        )
        rows = list(response.data or [])
        if not rows:
            return None
        metrics = rows[0].get("metrics")
        return dict(metrics) if isinstance(metrics, dict) else None
    except Exception as exc:
        LOG.warning("supabase spot_reports load failed: %s", exc)
        return None


def _persist_unlocked() -> str:
    payload = _snapshot()
    local_ok = False
    try:
        _write_local(payload)
        local_ok = True
    except Exception as exc:
        LOG.warning("local spot_reports save failed: %s", exc)
    remote_ok = _save_supabase(payload)
    if remote_ok:
        return "supabase"
    if local_ok:
        return "local"
    return "memory"


def _hydrate_unlocked() -> None:
    global _HYDRATED, _PERSIST_SOURCE
    if _HYDRATED:
        return
    remote = _load_supabase()
    if _apply_snapshot(remote):
        _PERSIST_SOURCE = "supabase"
        _HYDRATED = True
        try:
            _write_local(_snapshot())
        except Exception:
            pass
        return
    local = _read_local()
    if _apply_snapshot(local):
        _PERSIST_SOURCE = "local"
        _HYDRATED = True
        return
    _PERSIST_SOURCE = "memory"
    _HYDRATED = True


def submit_spot_report(
    *,
    card_id: str,
    note: str | None = None,
    spot: float | None = None,
    session: str | None = None,
) -> dict[str, Any]:
    global _PERSIST_SOURCE
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
        _hydrate_unlocked()
        _REPORTS.appendleft(entry)
        _PERSIST_SOURCE = _persist_unlocked()
        return dict(entry)


def list_spot_reports(
    *,
    status: str | None = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    with _LOCK:
        _hydrate_unlocked()
        rows = list(_REPORTS)
    if status:
        want = str(status).strip().lower()
        rows = [r for r in rows if str(r.get("status")) == want]
    return [dict(r) for r in rows[: max(1, min(100, int(limit)))]]


def set_report_status(report_id: str, status: LOG_STATUS) -> dict[str, Any] | None:
    global _PERSIST_SOURCE
    rid = str(report_id or "").strip()
    with _LOCK:
        _hydrate_unlocked()
        for row in _REPORTS:
            if str(row.get("id")) == rid:
                row["status"] = status
                row["updated_at"] = time.time()
                _PERSIST_SOURCE = _persist_unlocked()
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


def latest_report_for_card(card_id: str) -> dict[str, Any] | None:
    """Newest report for a card (queue is newest-first). Public detail closure."""
    cid = str(card_id or "").strip()
    if not cid:
        return None
    with _LOCK:
        _hydrate_unlocked()
        for row in _REPORTS:
            if str(row.get("card_id") or "") == cid:
                return dict(row)
    return None


def spot_report_summary() -> dict[str, Any]:
    with _LOCK:
        _hydrate_unlocked()
        rows = list(_REPORTS)
        source = _PERSIST_SOURCE
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
        "persisted": source in {"local", "supabase"},
        "source": source,
    }


def reset_spot_reports_for_tests() -> None:
    global _HYDRATED, _PERSIST_SOURCE, _STARTED_AT
    with _LOCK:
        _REPORTS.clear()
        _STARTED_AT = time.time()
        _HYDRATED = True
        _PERSIST_SOURCE = "memory"
        try:
            if LOCAL_PATH.is_file():
                LOCAL_PATH.unlink()
        except Exception:
            pass

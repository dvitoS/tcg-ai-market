"""Soft-launch funnel counters (landing → DOTD → Pro → Radar/Trade).

Counts persist across API restarts via local JSON + optional Supabase
``model_artifacts`` row (same pattern as spot_qa). Events stay anonymous
(session id only) — no third-party analytics vendor required.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone
from typing import Any

from config import PROJECT_ROOT

LOG = logging.getLogger("tcg.funnel")

FUNNEL_ARTIFACT_ID = "soft_launch_funnel"
LOCAL_PATH = PROJECT_ROOT / ".data" / "funnel.json"

# Keep the allowlist tight so random noise cannot inflate the funnel.
ALLOWED_EVENTS = frozenset(
    {
        "landing_view",
        "landing_cta_dotd",
        "landing_cta_pro",
        "dotd_view",
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
        "spot_report",
    }
)

_LOCK = threading.Lock()
_COUNTS: Counter[str] = Counter()
_RECENT: deque[dict[str, Any]] = deque(maxlen=200)
_STARTED_AT = time.time()
_HYDRATED = False
_PERSIST_SOURCE = "memory"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot() -> dict[str, Any]:
    return {
        "counts": dict(_COUNTS),
        "recent": list(_RECENT)[:40],
        "updated_at": _utc_now(),
        "total": int(sum(_COUNTS.values())),
    }


def _apply_snapshot(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    counts = payload.get("counts")
    if not isinstance(counts, dict) or not counts:
        return False
    _COUNTS.clear()
    for key, value in counts.items():
        name = str(key or "").strip()
        if name not in ALLOWED_EVENTS:
            continue
        try:
            n = int(value)
        except (TypeError, ValueError):
            continue
        if n > 0:
            _COUNTS[name] = n
    recent = payload.get("recent")
    _RECENT.clear()
    if isinstance(recent, list):
        for item in recent[:200]:
            if isinstance(item, dict) and item.get("event") in ALLOWED_EVENTS:
                _RECENT.append(item)
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
        LOG.warning("local funnel read failed: %s", exc)
        return None


def _save_supabase(payload: dict[str, Any]) -> bool:
    try:
        from database import get_supabase

        client = get_supabase()
        row = {
            "id": FUNNEL_ARTIFACT_ID,
            "algo": "funnel",
            "blob_b64": "",
            "metrics": payload,
            "feature_columns": [],
            "trained_at": payload.get("updated_at") or _utc_now(),
        }
        client.table("model_artifacts").upsert(row, on_conflict="id").execute()
        return True
    except Exception as exc:
        LOG.warning("supabase funnel save failed: %s", exc)
        return False


def _load_supabase() -> dict[str, Any] | None:
    try:
        from database import get_supabase

        client = get_supabase()
        response = (
            client.table("model_artifacts")
            .select("metrics")
            .eq("id", FUNNEL_ARTIFACT_ID)
            .limit(1)
            .execute()
        )
        rows = list(response.data or [])
        if not rows:
            return None
        metrics = rows[0].get("metrics")
        return dict(metrics) if isinstance(metrics, dict) else None
    except Exception as exc:
        LOG.warning("supabase funnel load failed: %s", exc)
        return None


def _persist_unlocked() -> str:
    """Write snapshot; return storage label used."""
    payload = _snapshot()
    local_ok = False
    try:
        _write_local(payload)
        local_ok = True
    except Exception as exc:
        LOG.warning("local funnel save failed: %s", exc)
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
        # Mirror to local for faster next boot / offline ops.
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


def record_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate and record a batch of funnel events. Returns accept stats."""
    global _PERSIST_SOURCE
    accepted = 0
    rejected = 0
    with _LOCK:
        _hydrate_unlocked()
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
        if accepted:
            _PERSIST_SOURCE = _persist_unlocked()
    return {"accepted": accepted, "rejected": rejected}


def funnel_summary() -> dict[str, Any]:
    with _LOCK:
        _hydrate_unlocked()
        counts = dict(_COUNTS)
        recent = list(_RECENT)[:40]
        total = int(sum(_COUNTS.values()))
        source = _PERSIST_SOURCE
    return {
        "counts": counts,
        "total": total,
        "recent": recent,
        "uptime_s": round(time.time() - _STARTED_AT, 1),
        "allowed_events": sorted(ALLOWED_EVENTS),
        "persisted": source in {"local", "supabase"},
        "source": source,
    }


def reset_funnel_for_tests() -> None:
    global _HYDRATED, _PERSIST_SOURCE, _STARTED_AT
    with _LOCK:
        _COUNTS.clear()
        _RECENT.clear()
        _HYDRATED = True
        _PERSIST_SOURCE = "memory"
        _STARTED_AT = time.time()
        try:
            if LOCAL_PATH.is_file():
                LOCAL_PATH.unlink()
        except Exception:
            pass

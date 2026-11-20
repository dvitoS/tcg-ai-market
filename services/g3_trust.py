"""G3 spend-unlock trust metrics (refund / cancel citing wrong prices).

Soft-launch: Creem rarely sends structured refund reasons, so we combine:
- cancel/refund webhook outcomes + free-text reason classification
- wrong-spot report volume vs entitled Pro users

Gate target (ROADMAP): <2% of cancels/refunds cite wrong prices.

Counters persist across API restarts (local JSON + optional Supabase
``model_artifacts``), same pattern as ``services/funnel.py``.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from config import PROJECT_ROOT

LOG = logging.getLogger("tcg.g3_trust")

G3_ARTIFACT_ID = "g3_trust_counters"
LOCAL_PATH = PROJECT_ROOT / ".data" / "g3_trust.json"

_LOCK = threading.Lock()
_STARTED_AT = time.time()
_CANCEL_REASONS: Counter[str] = Counter()
_WRONG_PRICE_HITS = 0
_REFUND_EVENTS = 0
_CANCEL_EVENTS = 0
_HYDRATED = False
_PERSIST_SOURCE = "memory"

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
    return text[:80].lower()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot() -> dict[str, Any]:
    return {
        "cancel_events": int(_CANCEL_EVENTS),
        "refund_events": int(_REFUND_EVENTS),
        "wrong_price_hits": int(_WRONG_PRICE_HITS),
        "reason_buckets": dict(_CANCEL_REASONS),
        "updated_at": _utc_now(),
    }


def _apply_snapshot(payload: dict[str, Any] | None) -> bool:
    global _WRONG_PRICE_HITS, _REFUND_EVENTS, _CANCEL_EVENTS
    if not payload or not isinstance(payload, dict):
        return False
    try:
        cancels = int(payload.get("cancel_events") or 0)
        refunds = int(payload.get("refund_events") or 0)
        wrong = int(payload.get("wrong_price_hits") or 0)
    except (TypeError, ValueError):
        return False
    if cancels < 0 or refunds < 0 or wrong < 0:
        return False
    reasons_raw = payload.get("reason_buckets")
    reasons: Counter[str] = Counter()
    if isinstance(reasons_raw, dict):
        for key, value in reasons_raw.items():
            name = str(key or "").strip()
            if not name:
                continue
            try:
                n = int(value)
            except (TypeError, ValueError):
                continue
            if n > 0:
                reasons[name] = n
    _CANCEL_EVENTS = cancels
    _REFUND_EVENTS = refunds
    _WRONG_PRICE_HITS = wrong
    _CANCEL_REASONS.clear()
    _CANCEL_REASONS.update(reasons)
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
        LOG.warning("local g3_trust read failed: %s", exc)
        return None


def _save_supabase(payload: dict[str, Any]) -> bool:
    try:
        from database import get_supabase

        client = get_supabase()
        row = {
            "id": G3_ARTIFACT_ID,
            "algo": "g3_trust",
            "blob_b64": "",
            "metrics": payload,
            "feature_columns": [],
            "trained_at": payload.get("updated_at") or _utc_now(),
        }
        client.table("model_artifacts").upsert(row, on_conflict="id").execute()
        return True
    except Exception as exc:
        LOG.warning("supabase g3_trust save failed: %s", exc)
        return False


def _load_supabase() -> dict[str, Any] | None:
    try:
        from database import get_supabase

        client = get_supabase()
        response = (
            client.table("model_artifacts")
            .select("metrics")
            .eq("id", G3_ARTIFACT_ID)
            .limit(1)
            .execute()
        )
        rows = list(response.data or [])
        if not rows:
            return None
        metrics = rows[0].get("metrics")
        return dict(metrics) if isinstance(metrics, dict) else None
    except Exception as exc:
        LOG.warning("supabase g3_trust load failed: %s", exc)
        return None


def _persist_unlocked() -> str:
    payload = _snapshot()
    local_ok = False
    try:
        _write_local(payload)
        local_ok = True
    except Exception as exc:
        LOG.warning("local g3_trust save failed: %s", exc)
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


def record_cancel_or_refund(
    *,
    kind: str,
    reason: str | None = None,
    event_type: str | None = None,
) -> None:
    """Record a cancel/refund webhook for the G3 trust gate."""
    global _WRONG_PRICE_HITS, _REFUND_EVENTS, _CANCEL_EVENTS, _PERSIST_SOURCE
    bucket = _bucket_reason(reason)
    hit = bucket == "wrong_price"
    with _LOCK:
        _hydrate_unlocked()
        if kind == "refund":
            _REFUND_EVENTS += 1
        else:
            _CANCEL_EVENTS += 1
        _CANCEL_REASONS[bucket] += 1
        if hit:
            _WRONG_PRICE_HITS += 1
        if event_type:
            _CANCEL_REASONS[f"event:{event_type}"] += 1
        _PERSIST_SOURCE = _persist_unlocked()


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
        _hydrate_unlocked()
        reasons = dict(_CANCEL_REASONS)
        wrong_hits = int(_WRONG_PRICE_HITS)
        refunds = int(_REFUND_EVENTS)
        cancels = int(_CANCEL_EVENTS)
        uptime_s = round(time.time() - _STARTED_AT, 1)
        source = _PERSIST_SOURCE

    cited = cancels + refunds
    wrong_price_pct = (
        round(100.0 * wrong_hits / cited, 2) if cited > 0 else None
    )
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
        "persisted": source in {"local", "supabase"},
        "source": source,
    }


def reset_g3_trust_for_tests() -> None:
    global _WRONG_PRICE_HITS, _REFUND_EVENTS, _CANCEL_EVENTS, _STARTED_AT
    global _HYDRATED, _PERSIST_SOURCE
    with _LOCK:
        _CANCEL_REASONS.clear()
        _WRONG_PRICE_HITS = 0
        _REFUND_EVENTS = 0
        _CANCEL_EVENTS = 0
        _STARTED_AT = time.time()
        _HYDRATED = True
        _PERSIST_SOURCE = "memory"
        try:
            if LOCAL_PATH.is_file():
                LOCAL_PATH.unlink()
        except Exception:
            pass

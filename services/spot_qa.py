"""Spot / history QA snapshot for Soft Ink data-health (Phase C2)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from config import PROJECT_ROOT

LOG = logging.getLogger("tcg.spot_qa")

SPOT_QA_ID = "spot_qa"
LOCAL_PATH = PROJECT_ROOT / ".data" / "spot_qa.json"
FRESH_MAX_AGE_DAYS = 3
FRESH_MIN_POINTS = 7  # aligned with api.price_sources_service


def _write_local(payload: dict[str, Any]) -> None:
    LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_PATH.write_text(
        __import__("json").dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _read_local() -> dict[str, Any] | None:
    if not LOCAL_PATH.is_file():
        return None
    try:
        return dict(__import__("json").loads(LOCAL_PATH.read_text(encoding="utf-8")))
    except Exception as exc:
        LOG.warning("local spot_qa read failed: %s", exc)
        return None


def save_spot_qa_snapshot(payload: dict[str, Any]) -> bool:
    """Persist QA metrics to Supabase model_artifacts + local JSON."""
    body = dict(payload)
    body.setdefault("captured_at", datetime.now(timezone.utc).isoformat())
    try:
        _write_local(body)
    except Exception as exc:
        LOG.warning("local spot_qa save failed: %s", exc)

    try:
        from database import get_supabase

        client = get_supabase()
        row = {
            "id": SPOT_QA_ID,
            "algo": "spot_qa",
            "blob_b64": "",
            "metrics": body,
            "feature_columns": [],
            "trained_at": body["captured_at"],
        }
        client.table("model_artifacts").upsert(row, on_conflict="id").execute()
        return True
    except Exception as exc:
        LOG.warning("supabase spot_qa save failed: %s", exc)
        return LOCAL_PATH.is_file()


def load_spot_qa_snapshot() -> dict[str, Any] | None:
    try:
        from database import get_supabase

        client = get_supabase()
        response = (
            client.table("model_artifacts")
            .select("metrics,trained_at")
            .eq("id", SPOT_QA_ID)
            .limit(1)
            .execute()
        )
        rows = list(response.data or [])
        if rows:
            metrics = dict(rows[0].get("metrics") or {})
            if rows[0].get("trained_at") and "captured_at" not in metrics:
                metrics["captured_at"] = rows[0]["trained_at"]
            return metrics
    except Exception as exc:
        LOG.warning("supabase spot_qa load failed: %s", exc)
    return _read_local()


def compute_live_spot_qa() -> dict[str, Any]:
    """Always-on metrics from board + price_history presence (no JustTCG calls)."""
    out: dict[str, Any] = {
        "cards_total": 0,
        "cards_with_history": 0,
        "history_coverage_pct": 0.0,
        "quotes_total": 0,
        "sure_rows": 0,
        "spot_quarantine_rows": 0,
        "spot_poison_clusters": 0,
        "spot_poison_cluster_sample": [],
        "board_source": "empty",
    }
    try:
        from database import distinct_history_card_ids, table_count

        cards_total = int(table_count("cards") or 0)
        with_hist = len(distinct_history_card_ids())
        out["cards_total"] = cards_total
        out["cards_with_history"] = with_hist
        out["history_coverage_pct"] = (
            round(100.0 * with_hist / cards_total, 2) if cards_total else 0.0
        )
    except Exception as exc:
        LOG.warning("spot_qa history coverage failed: %s", exc)

    try:
        from api.catalog_service import load_board

        board, source = load_board()
        out["board_source"] = source
        if board is not None and not board.empty:
            import pandas as pd

            out["quotes_total"] = int(len(board))
            mask = pd.Series(True, index=board.index)
            if "confidence_ok" in board.columns:
                mask &= board["confidence_ok"].fillna(False).astype(bool)
            if "conformal_ok" in board.columns:
                mask &= board["conformal_ok"].fillna(False).astype(bool)
            out["sure_rows"] = int(mask.sum())
            try:
                from services.spot_sanity import summarize_poison_clusters

                if "spot_quarantine" in board.columns:
                    out["spot_quarantine_rows"] = int(
                        board["spot_quarantine"].fillna(False).astype(bool).sum()
                    )
                sample = summarize_poison_clusters(board, limit=6)
                out["spot_poison_cluster_sample"] = sample
                out["spot_poison_clusters"] = int(len(sample))
                if out["spot_quarantine_rows"] == 0 and sample:
                    out["spot_quarantine_rows"] = int(sum(int(r["count"]) for r in sample))
            except Exception as qexc:
                LOG.warning("spot_qa quarantine metrics failed: %s", qexc)
    except Exception as exc:
        LOG.warning("spot_qa sure_rows failed: %s", exc)

    return out


def compute_fresh_history_pct() -> float | None:
    """% of catalog cards with a price_history point in the last FRESH_MAX_AGE_DAYS."""
    try:
        from database import distinct_history_card_ids_since, table_count

        cards_total = int(table_count("cards") or 0)
        if cards_total <= 0:
            return 0.0
        since = (date.today() - timedelta(days=FRESH_MAX_AGE_DAYS)).isoformat()
        fresh = len(distinct_history_card_ids_since(since))
        return round(100.0 * fresh / cards_total, 2)
    except Exception as exc:
        LOG.warning("spot_qa fresh_history_pct failed: %s", exc)
        return None


def build_and_save_snapshot(
    *,
    unmatched_sets: list[dict[str, str]] | None = None,
    justtcg_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose nightly snapshot: live coverage + unmatched + fresh %."""
    live = compute_live_spot_qa()
    unmatched = list(unmatched_sets or [])
    unmatched_codes = sorted(
        {
            str(row.get("set_code") or "").strip()
            for row in unmatched
            if isinstance(row, dict) and str(row.get("set_code") or "").strip()
        }
    )
    fresh = compute_fresh_history_pct()
    payload = {
        **live,
        "fresh_history_pct": fresh,
        "unmatched_sets_count": len(unmatched),
        "unmatched_sets_sample": unmatched[:12],
        # Full code list so the next nightly can skip wasted JustTCG work.
        "unmatched_set_codes": unmatched_codes,
        "justtcg_updated": int((justtcg_stats or {}).get("updated") or 0),
        "justtcg_skipped": int((justtcg_stats or {}).get("skipped") or 0),
        "justtcg_requests": int((justtcg_stats or {}).get("justtcg_requests") or 0),
        "fresh_max_age_days": FRESH_MAX_AGE_DAYS,
        "fresh_min_points": FRESH_MIN_POINTS,
    }
    save_spot_qa_snapshot(payload)
    return payload


def data_health_spot_fields() -> dict[str, Any]:
    """Merge live metrics with last nightly snapshot for /api/data-health."""
    live = compute_live_spot_qa()
    snap = load_spot_qa_snapshot() or {}
    return {
        "cards_total": int(live.get("cards_total") or snap.get("cards_total") or 0),
        "cards_with_history": int(
            live.get("cards_with_history") or snap.get("cards_with_history") or 0
        ),
        "history_coverage_pct": float(
            live.get("history_coverage_pct")
            if live.get("cards_total")
            else snap.get("history_coverage_pct")
            or 0.0
        ),
        "fresh_history_pct": (
            float(snap["fresh_history_pct"])
            if snap.get("fresh_history_pct") is not None
            else None
        ),
        "sure_rows": int(live.get("sure_rows") or 0),
        "quotes_total": int(live.get("quotes_total") or 0),
        "spot_quarantine_rows": int(
            live.get("spot_quarantine_rows")
            if live.get("spot_quarantine_rows") is not None
            else snap.get("spot_quarantine_rows")
            or 0
        ),
        "spot_poison_clusters": int(
            live.get("spot_poison_clusters")
            if live.get("spot_poison_clusters") is not None
            else snap.get("spot_poison_clusters")
            or 0
        ),
        "spot_poison_cluster_sample": list(
            live.get("spot_poison_cluster_sample")
            or snap.get("spot_poison_cluster_sample")
            or []
        )[:6],
        "unmatched_sets_count": (
            int(snap["unmatched_sets_count"])
            if snap.get("unmatched_sets_count") is not None
            else None
        ),
        "unmatched_sets_sample": list(snap.get("unmatched_sets_sample") or [])[:12],
        "spot_qa_captured_at": snap.get("captured_at"),
        "board_source": str(live.get("board_source") or snap.get("board_source") or "empty"),
        "nightly_slo_ok": (
            bool(snap["nightly_slo_ok"]) if snap.get("nightly_slo_ok") is not None else None
        ),
        "nightly_elapsed_s": (
            float(snap["nightly_elapsed_s"])
            if snap.get("nightly_elapsed_s") is not None
            else None
        ),
        "quotes_written": (
            int(snap["quotes_written"]) if snap.get("quotes_written") is not None else None
        ),
    }

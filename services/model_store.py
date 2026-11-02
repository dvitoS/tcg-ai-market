"""Persist / load the XGBoost artifact (Supabase + local fallback)."""

from __future__ import annotations

import base64
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT

LOG = logging.getLogger("tcg.model_store")

ARTIFACT_ID = "latest"
TABLE = "model_artifacts"
LOCAL_DIR = PROJECT_ROOT / ".data" / "models"
LOCAL_MODEL = LOCAL_DIR / "xgb_latest.joblib"
LOCAL_META = LOCAL_DIR / "xgb_latest.meta.json"


def _joblib():
    import joblib

    return joblib


def _encode_model(model: Any) -> str:
    buf = io.BytesIO()
    _joblib().dump(model, buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _decode_model(blob_b64: str) -> Any:
    raw = base64.b64decode(blob_b64.encode("ascii"))
    return _joblib().load(io.BytesIO(raw))


def _write_local(model: Any, *, metrics: dict[str, Any] | None, feature_columns: list[str]) -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    _joblib().dump(model, LOCAL_MODEL)
    meta = {
        "metrics": metrics or {},
        "feature_columns": feature_columns,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    LOCAL_META.write_text(json.dumps(meta), encoding="utf-8")


def _read_local() -> tuple[Any, dict[str, Any]] | None:
    if not LOCAL_MODEL.is_file():
        return None
    try:
        model = _joblib().load(LOCAL_MODEL)
        meta: dict[str, Any] = {}
        if LOCAL_META.is_file():
            meta = json.loads(LOCAL_META.read_text(encoding="utf-8"))
        return model, meta
    except Exception as exc:
        LOG.warning("local model load failed: %s", exc)
        return None


def save_model_artifact(
    model: Any,
    *,
    metrics: dict[str, Any] | None = None,
    feature_columns: list[str] | None = None,
) -> bool:
    """Upsert model to Supabase; always mirror locally when possible."""
    from ai_xgboost import FEATURE_COLUMNS

    cols = list(feature_columns or FEATURE_COLUMNS)
    metrics = dict(metrics or {})
    try:
        _write_local(model, metrics=metrics, feature_columns=cols)
    except Exception as exc:
        LOG.warning("local model save failed: %s", exc)

    try:
        from database import get_supabase

        client = get_supabase()
        row = {
            "id": ARTIFACT_ID,
            "algo": "xgboost",
            "blob_b64": _encode_model(model),
            "metrics": metrics,
            "feature_columns": cols,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        }
        client.table(TABLE).upsert(row, on_conflict="id").execute()
        return True
    except Exception as exc:
        LOG.warning("supabase model save failed: %s", exc)
        return LOCAL_MODEL.is_file()


def load_model_artifact() -> tuple[Any, dict[str, Any]] | None:
    """Prefer Supabase artifact; fall back to local joblib file."""
    try:
        from database import get_supabase

        client = get_supabase()
        response = (
            client.table(TABLE)
            .select("blob_b64,metrics,feature_columns,trained_at,algo")
            .eq("id", ARTIFACT_ID)
            .limit(1)
            .execute()
        )
        rows = list(response.data or [])
        if rows and rows[0].get("blob_b64"):
            model = _decode_model(str(rows[0]["blob_b64"]))
            meta = {
                "metrics": rows[0].get("metrics") or {},
                "feature_columns": rows[0].get("feature_columns") or [],
                "trained_at": rows[0].get("trained_at"),
                "algo": rows[0].get("algo"),
            }
            # Refresh local mirror for faster subsequent boots.
            try:
                _write_local(
                    model,
                    metrics=dict(meta.get("metrics") or {}),
                    feature_columns=list(meta.get("feature_columns") or []),
                )
            except Exception:
                pass
            return model, meta
    except Exception as exc:
        LOG.warning("supabase model load failed: %s", exc)

    return _read_local()

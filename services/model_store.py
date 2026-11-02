"""Persist / load the XGBoost artifact (Supabase + local fallback)."""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT

LOG = logging.getLogger("tcg.model_store")

ARTIFACT_ID = "latest"
TABLE = "model_artifacts"
LOCAL_DIR = PROJECT_ROOT / ".data" / "models"


def _safe_id(artifact_id: str) -> str:
    raw = str(artifact_id or ARTIFACT_ID).strip() or ARTIFACT_ID
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", raw)[:64]


def _local_paths(artifact_id: str) -> tuple[Path, Path]:
    safe = _safe_id(artifact_id)
    return LOCAL_DIR / f"xgb_{safe}.joblib", LOCAL_DIR / f"xgb_{safe}.meta.json"


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


def _write_local(
    model: Any,
    *,
    metrics: dict[str, Any] | None,
    feature_columns: list[str],
    artifact_id: str = ARTIFACT_ID,
) -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    model_path, meta_path = _local_paths(artifact_id)
    _joblib().dump(model, model_path)
    meta = {
        "metrics": metrics or {},
        "feature_columns": feature_columns,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "artifact_id": _safe_id(artifact_id),
    }
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


def _read_local(artifact_id: str = ARTIFACT_ID) -> tuple[Any, dict[str, Any]] | None:
    model_path, meta_path = _local_paths(artifact_id)
    if not model_path.is_file():
        # Back-compat: original 7d filenames.
        if _safe_id(artifact_id) == ARTIFACT_ID:
            legacy_model = LOCAL_DIR / "xgb_latest.joblib"
            legacy_meta = LOCAL_DIR / "xgb_latest.meta.json"
            if legacy_model.is_file():
                model_path, meta_path = legacy_model, legacy_meta
            else:
                return None
        else:
            return None
    try:
        model = _joblib().load(model_path)
        meta: dict[str, Any] = {}
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return model, meta
    except Exception as exc:
        LOG.warning("local model load failed (%s): %s", artifact_id, exc)
        return None


def save_model_artifact(
    model: Any,
    *,
    metrics: dict[str, Any] | None = None,
    feature_columns: list[str] | None = None,
    artifact_id: str = ARTIFACT_ID,
) -> bool:
    """Upsert model to Supabase; always mirror locally when possible."""
    from ai_xgboost import FEATURE_COLUMNS

    art_id = _safe_id(artifact_id)
    cols = list(feature_columns or FEATURE_COLUMNS)
    metrics = dict(metrics or {})
    model_path, _meta_path = _local_paths(art_id)
    try:
        _write_local(
            model, metrics=metrics, feature_columns=cols, artifact_id=art_id
        )
    except Exception as exc:
        LOG.warning("local model save failed (%s): %s", art_id, exc)

    try:
        from database import get_supabase

        client = get_supabase()
        row = {
            "id": art_id,
            "algo": "xgboost",
            "blob_b64": _encode_model(model),
            "metrics": metrics,
            "feature_columns": cols,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        }
        client.table(TABLE).upsert(row, on_conflict="id").execute()
        return True
    except Exception as exc:
        LOG.warning("supabase model save failed (%s): %s", art_id, exc)
        return model_path.is_file()


def load_model_artifact(
    artifact_id: str = ARTIFACT_ID,
) -> tuple[Any, dict[str, Any]] | None:
    """Prefer Supabase artifact; fall back to local joblib file."""
    art_id = _safe_id(artifact_id)
    try:
        from database import get_supabase

        client = get_supabase()
        response = (
            client.table(TABLE)
            .select("blob_b64,metrics,feature_columns,trained_at,algo")
            .eq("id", art_id)
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
                "artifact_id": art_id,
            }
            try:
                _write_local(
                    model,
                    metrics=dict(meta.get("metrics") or {}),
                    feature_columns=list(meta.get("feature_columns") or []),
                    artifact_id=art_id,
                )
            except Exception:
                pass
            return model, meta
    except Exception as exc:
        LOG.warning("supabase model load failed (%s): %s", art_id, exc)

    return _read_local(art_id)

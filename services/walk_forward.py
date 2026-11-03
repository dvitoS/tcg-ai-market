"""Expanding-window walk-forward evaluation for the return model."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error

from ai_xgboost import (
    FEATURE_COLUMNS,
    RETURN_HOLD_BAND,
    _signed_return,
    train_xgboost,
)


def _fold_date_bounds(
    dates: np.ndarray,
    *,
    n_folds: int,
    min_train_frac: float = 0.4,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Chronological test windows after an initial train block."""
    n = len(dates)
    if n < 6 or n_folds < 1:
        return []
    train_end_idx = max(2, int(n * float(min_train_frac)))
    train_end_idx = min(train_end_idx, n - n_folds - 1)
    if train_end_idx < 2:
        return []
    test_dates = dates[train_end_idx:]
    if len(test_dates) < n_folds:
        return []
    # Split remaining dates into n_folds contiguous chunks.
    edges = np.linspace(0, len(test_dates), n_folds + 1, dtype=int)
    bounds: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for i in range(n_folds):
        start = test_dates[edges[i]]
        # End exclusive: next chunk start, or day after last date.
        if i + 1 < n_folds:
            end = test_dates[edges[i + 1]]
        else:
            end = pd.Timestamp(test_dates[-1]) + pd.Timedelta(days=1)
        bounds.append((pd.Timestamp(start), pd.Timestamp(end)))
    return bounds


def score_fold_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    hold_band: float,
) -> dict[str, float]:
    y = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    rmse = float(np.sqrt(mean_squared_error(y, pred)))
    naive_rmse = float(np.sqrt(mean_squared_error(y, np.zeros_like(y))))
    actual_dir = _signed_return(y, hold_band=hold_band)
    pred_dir = _signed_return(pred, hold_band=hold_band)
    movable = actual_dir != 0
    if movable.any():
        direction_acc = float((actual_dir[movable] == pred_dir[movable]).mean() * 100.0)
        direction_n = float(int(movable.sum()))
    else:
        direction_acc = float("nan")
        direction_n = 0.0
    return {
        "rmse": rmse,
        "naive_rmse": naive_rmse,
        "rmse_vs_naive": float(rmse / naive_rmse) if naive_rmse > 0 else float("nan"),
        "direction_accuracy_pct": direction_acc,
        "direction_n": direction_n,
        "pred_flat_pct": float((pred_dir == 0).mean() * 100.0),
        "n": float(len(y)),
    }


def walk_forward_evaluate(
    df: pd.DataFrame,
    *,
    n_folds: int = 4,
    min_train_rows: int = 80,
    min_test_rows: int = 25,
    hold_band: float | None = None,
    min_train_frac: float = 0.4,
    quiet: bool = True,
) -> dict[str, Any]:
    """Expanding-window walk-forward on ``target_return``.

    For each fold: train on all rows with ``date < fold_start``,
    test on ``fold_start <= date < fold_end``.
    """
    band = float(RETURN_HOLD_BAND if hold_band is None else hold_band)
    empty: dict[str, Any] = {
        "wf_folds": 0,
        "wf_skipped": True,
    }
    if df is None or df.empty or "date" not in df.columns:
        return empty
    if "target_return" not in df.columns:
        return empty
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        empty["wf_error"] = f"missing features: {missing[:3]}"
        return empty

    work = df.dropna(subset=FEATURE_COLUMNS + ["target_return", "date"]).copy()
    work["date"] = pd.to_datetime(work["date"])
    dates = np.sort(work["date"].unique())
    bounds = _fold_date_bounds(dates, n_folds=n_folds, min_train_frac=min_train_frac)
    if not bounds:
        return empty

    fold_metrics: list[dict[str, float]] = []
    for i, (start, end) in enumerate(bounds, start=1):
        train_mask = work["date"] < start
        test_mask = (work["date"] >= start) & (work["date"] < end)
        n_train = int(train_mask.sum())
        n_test = int(test_mask.sum())
        if n_train < min_train_rows or n_test < min_test_rows:
            continue
        X_train = work.loc[train_mask, FEATURE_COLUMNS]
        y_train = work.loc[train_mask, "target_return"]
        X_test = work.loc[test_mask, FEATURE_COLUMNS]
        y_test = work.loc[test_mask, "target_return"]
        model = train_xgboost(X_train, y_train, quiet=quiet)
        preds = np.asarray(model.predict(X_test), dtype=float)
        scored = score_fold_predictions(
            np.asarray(y_test, dtype=float),
            preds,
            hold_band=band,
        )
        scored["fold"] = float(i)
        scored["train_rows"] = float(n_train)
        scored["test_rows"] = float(n_test)
        fold_metrics.append(scored)
        if not quiet:
            print(
                f"WF fold {i}: train={n_train} test={n_test} "
                f"dir={scored['direction_accuracy_pct']:.1f}% "
                f"rmse/naive={scored['rmse_vs_naive']:.3f} "
                f"[{start.date()} → {end.date()})"
            )

    if not fold_metrics:
        return empty

    def _mean(key: str) -> float:
        vals = [m[key] for m in fold_metrics if m.get(key) == m.get(key)]
        return float(np.mean(vals)) if vals else float("nan")

    # Pooled direction: weight by direction_n.
    dir_num = 0.0
    dir_den = 0.0
    for m in fold_metrics:
        n = float(m.get("direction_n") or 0.0)
        acc = m.get("direction_accuracy_pct")
        if n > 0 and acc == acc:
            dir_num += acc * n
            dir_den += n
    pooled_dir = float(dir_num / dir_den) if dir_den > 0 else float("nan")

    out: dict[str, Any] = {
        "wf_folds": int(len(fold_metrics)),
        "wf_skipped": False,
        "wf_direction_accuracy_pct": pooled_dir,
        "wf_direction_accuracy_mean_pct": _mean("direction_accuracy_pct"),
        "wf_rmse_vs_naive": _mean("rmse_vs_naive"),
        "wf_rmse": _mean("rmse"),
        "wf_pred_flat_pct": _mean("pred_flat_pct"),
        "wf_direction_n": float(dir_den),
        "wf_fold_details": fold_metrics,
    }
    if not quiet:
        print(
            f"=== Walk-forward ({out['wf_folds']} folds) ===\n"
            f"Direction (pooled): {pooled_dir:.1f}%\n"
            f"RMSE / naive (mean): {out['wf_rmse_vs_naive']:.3f}"
        )
    return out


def walk_forward_summary_metrics(result: dict[str, Any]) -> dict[str, float | int]:
    """Flatten WF result for model artifact / nightly logs (no fold lists)."""
    if not result or result.get("wf_skipped"):
        return {"wf_folds": 0}
    out: dict[str, float | int] = {"wf_folds": int(result.get("wf_folds") or 0)}
    for key in (
        "wf_direction_accuracy_pct",
        "wf_direction_accuracy_mean_pct",
        "wf_rmse_vs_naive",
        "wf_rmse",
        "wf_pred_flat_pct",
        "wf_direction_n",
    ):
        val = result.get(key)
        if val is not None and val == val:
            out[key] = float(val)
    return out

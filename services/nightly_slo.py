"""Nightly SLO helpers — elapsed budgets + quotes-written gate (Phase C3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Any


@dataclass
class PhaseTimer:
    name: str
    started: float = field(default_factory=monotonic)
    ended: float | None = None
    ok: bool = True
    error: str | None = None

    def finish(self, *, ok: bool = True, error: str | None = None) -> float:
        self.ended = monotonic()
        self.ok = ok
        self.error = error
        return self.elapsed_s

    @property
    def elapsed_s(self) -> float:
        end = self.ended if self.ended is not None else monotonic()
        return max(0.0, end - self.started)


def evaluate_nightly_slo(
    *,
    elapsed_s: float,
    max_seconds: int,
    quotes_written: int,
    failures: list[str],
    sure_rows: int | None = None,
    min_sure_rows: int = 1,
) -> dict[str, Any]:
    """Return SLO verdict. Quotes must refresh; wall clock must stay under soft max.

    When ``sure_rows`` is provided (post-retrain board sample), require at least
    ``min_sure_rows`` sure quotes so a useless empty conformal board cannot
    green-light marketing/ops (M0.5).
    """
    reasons: list[str] = []
    if quotes_written <= 0:
        reasons.append("quotes_not_written")
    if "retrain" in failures:
        reasons.append("retrain_failed")
    if elapsed_s > float(max_seconds):
        reasons.append("elapsed_over_budget")
    if sure_rows is not None and int(sure_rows) < int(min_sure_rows):
        reasons.append("sure_board_empty")
    ok = len(reasons) == 0
    return {
        "slo_ok": ok,
        "slo_reasons": reasons,
        "elapsed_s": round(float(elapsed_s), 1),
        "max_seconds": int(max_seconds),
        "quotes_written": int(quotes_written),
        "sure_rows": None if sure_rows is None else int(sure_rows),
    }

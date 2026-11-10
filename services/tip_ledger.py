"""Radar tip ledger — forward-evaluate sure UNDER/OVER after the forecast horizon.

Stores daily sure-desk tip samples on the spot_qa snapshot. Soft Ink Trust
scores only tips old enough that the forward window has closed — never trailing
returns vs today's tip (that proxy was misleading).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd

LOG = logging.getLogger("tcg.tip_ledger")

LEDGER_KEY = "radar_tip_ledger"
_MAX_TIPS = 4000
_KEEP_DAYS = 60


def _today() -> date:
    return date.today()


def tip_as_of(raw: Any) -> date | None:
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def load_tip_ledger() -> list[dict[str, Any]]:
    try:
        from services.spot_qa import load_spot_qa_snapshot

        snap = load_spot_qa_snapshot() or {}
        rows = list(snap.get(LEDGER_KEY) or [])
        return [r for r in rows if isinstance(r, dict)]
    except Exception as exc:
        LOG.warning("load tip ledger failed: %s", exc)
        return []


def save_tip_ledger(tips: list[dict[str, Any]]) -> bool:
    try:
        from services.spot_qa import load_spot_qa_snapshot, save_spot_qa_snapshot

        snap = load_spot_qa_snapshot() or {}
        snap[LEDGER_KEY] = list(tips)
        return bool(save_spot_qa_snapshot(snap))
    except Exception as exc:
        LOG.warning("save tip ledger failed: %s", exc)
        return False


def prune_ledger(tips: list[dict[str, Any]], *, keep_days: int = _KEEP_DAYS) -> list[dict[str, Any]]:
    floor = _today() - timedelta(days=max(14, int(keep_days)))
    kept: list[dict[str, Any]] = []
    for tip in tips:
        as_of = tip_as_of(tip.get("as_of"))
        if as_of is None or as_of < floor:
            continue
        kept.append(tip)
    if len(kept) > _MAX_TIPS:
        kept = kept[-_MAX_TIPS:]
    return kept


def record_sure_tips(
    tips: list[dict[str, Any]],
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Replace today's ledger slice with ``tips`` and persist."""
    day = (as_of or _today()).isoformat()
    ledger = [t for t in load_tip_ledger() if str(t.get("as_of") or "")[:10] != day]
    cleaned: list[dict[str, Any]] = []
    for tip in tips:
        cid = str(tip.get("card_id") or "").strip()
        side = str(tip.get("side") or "").upper()
        if not cid or side not in {"UNDER", "OVER"}:
            continue
        cleaned.append(
            {
                "card_id": cid,
                "side": side,
                "edge_pct": tip.get("edge_pct"),
                "pred_lo_pct": tip.get("pred_lo_pct"),
                "pred_hi_pct": tip.get("pred_hi_pct"),
                "as_of": day,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    ledger.extend(cleaned)
    ledger = prune_ledger(ledger)
    ok = save_tip_ledger(ledger)
    return {"saved": ok, "as_of": day, "tips": len(cleaned), "ledger_n": len(ledger)}


def price_on_or_before(frame: pd.DataFrame, day: date) -> float | None:
    if frame is None or frame.empty:
        return None
    prior = frame[frame["date"] <= pd.Timestamp(day)]
    if prior.empty:
        return None
    px = float(prior.iloc[-1]["price"])
    return px if px > 0 else None


def price_on_or_after(frame: pd.DataFrame, day: date) -> float | None:
    if frame is None or frame.empty:
        return None
    later = frame[frame["date"] >= pd.Timestamp(day)]
    if not later.empty:
        px = float(later.iloc[0]["price"])
        return px if px > 0 else None
    # Fall back to last available after as_of if horizon not fully closed in data.
    prior = frame[frame["date"] <= pd.Timestamp(day)]
    if prior.empty:
        return None
    px = float(prior.iloc[-1]["price"])
    return px if px > 0 else None


def forward_return_pct(
    frame: pd.DataFrame,
    *,
    as_of: date,
    horizon_days: int,
) -> float | None:
    """Price change from as_of → as_of+horizon (forward only)."""
    start = price_on_or_before(frame, as_of)
    end_day = as_of + timedelta(days=int(horizon_days))
    # Require the series to reach near the end of the window.
    last = frame.iloc[-1]["date"]
    last_day = pd.Timestamp(last).date() if hasattr(last, "date") else tip_as_of(last)
    if last_day is None or last_day < end_day - timedelta(days=1):
        # Allow 1-day slack for missing weekends/holidays in daily series.
        if last_day is None or last_day < as_of + timedelta(days=max(2, horizon_days - 2)):
            return None
    end = price_on_or_before(frame, end_day)
    if end is None:
        end = price_on_or_after(frame, end_day)
    if start is None or end is None or start <= 0:
        return None
    return (end - start) / start * 100.0


def score_forward_tips(
    by_card: dict[str, pd.DataFrame],
    *,
    horizon_days: int = 7,
    min_edge: float = 0.0,
    as_of_before: date | None = None,
) -> dict[str, Any]:
    """Score ledger tips whose forward window has closed."""
    floor = max(0.0, float(min_edge or 0.0))
    horizon = max(3, int(horizon_days))
    cutoff = as_of_before or (_today() - timedelta(days=horizon))
    base: dict[str, Any] = {
        "lookback_days": horizon,
        "horizon_days": horizon,
        "n": 0,
        "hit_rate_pct": None,
        "avg_move_pct": None,
        "under_n": 0,
        "over_n": 0,
        "min_edge": floor,
        "method": "forward_tip_ledger",
        "tighten_suggested": False,
        "pending_n": 0,
        "coverage_pct": None,
        "coverage_n": 0,
        "note": (
            f"Forward sure tips scored after {horizon}d. "
            "Not trailing returns vs today's tip."
        ),
    }
    ledger = load_tip_ledger()
    if not ledger:
        base["note"] = (
            "Collecting forward tip ledger — first Sure Radar hits appear after "
            f"~{horizon}d of nightly snapshots."
        )
        return base

    pending = 0
    hits = 0
    moves: list[float] = []
    under_n = 0
    over_n = 0
    covered = 0
    cov_n = 0

    for tip in ledger:
        as_of = tip_as_of(tip.get("as_of"))
        if as_of is None:
            continue
        edge = tip.get("edge_pct")
        try:
            edge_f = float(edge) if edge is not None else None
        except (TypeError, ValueError):
            edge_f = None
        if floor > 0 and edge_f is not None:
            side = str(tip.get("side") or "").upper()
            if side == "UNDER" and edge_f < floor:
                continue
            if side == "OVER" and edge_f > -floor:
                continue
        if as_of > cutoff:
            pending += 1
            continue
        card_id = str(tip.get("card_id") or "")
        hist = by_card.get(card_id)
        realized = (
            forward_return_pct(hist, as_of=as_of, horizon_days=horizon)
            if hist is not None
            else None
        )
        if realized is None:
            continue
        side = str(tip.get("side") or "").upper()
        moves.append(realized)
        if side == "UNDER":
            under_n += 1
            if realized > 0:
                hits += 1
        elif side == "OVER":
            over_n += 1
            if realized < 0:
                hits += 1
        else:
            continue

        lo = tip.get("pred_lo_pct")
        hi = tip.get("pred_hi_pct")
        try:
            lo_f = float(lo) if lo is not None else None
            hi_f = float(hi) if hi is not None else None
        except (TypeError, ValueError):
            lo_f, hi_f = None, None
        if lo_f is not None and hi_f is not None:
            cov_n += 1
            if min(lo_f, hi_f) <= realized <= max(lo_f, hi_f):
                covered += 1

    n = under_n + over_n
    base["n"] = n
    base["under_n"] = under_n
    base["over_n"] = over_n
    base["pending_n"] = pending
    if cov_n > 0:
        base["coverage_n"] = cov_n
        base["coverage_pct"] = round(100.0 * covered / cov_n, 2)
    if n > 0:
        hit_pct = round(100.0 * hits / n, 2)
        base["hit_rate_pct"] = hit_pct
        base["avg_move_pct"] = round(float(sum(moves) / len(moves)), 2) if moves else None
        base["tighten_suggested"] = bool(n >= 16 and hit_pct < 55.0)
        base["note"] = (
            f"Forward sure tips ({horizon}d after tip date)"
            + (f", min edge ≥{floor:g}%" if floor > 0 else "")
            + f". Pending younger tips: {pending}."
        )
    elif pending > 0:
        base["note"] = (
            f"Ledger has {pending} tip(s) still inside the {horizon}d forward window "
            "— scores unlock when that window closes."
        )
    else:
        base["note"] = (
            "Tip ledger has rows but none matched history for a closed forward window."
        )
    return base

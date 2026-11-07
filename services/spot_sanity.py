"""Spot / UNDER deal sanity guards.

JustTCG (and mirrored TCP) spots can land wildly wrong — e.g. bulk commons
stuck at identical high board prices — which then explode conformal UNDER edges.
These helpers gate ingest updates, quarantine board rows, and Radar UNDER.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from trading_signals import SIGNAL_HOLD

# Reject ingest when new spot vs prior market_price jumps outside [1/r, r].
SPOT_JUMP_MAX_RATIO = 8.0

# Radar UNDER surfacing (survives confidence + conformal gates).
RADAR_MAX_UNDER_EDGE_PCT = 50.0
RADAR_MIN_UNDER_SPOT = 1.5
RADAR_MAX_ABS_7D_CHANGE_PCT = 200.0

# Soft spot caps by rarity for UNDER only — poisoned commons at $60+ should not
# appear as "deals" even when the model edge looks moderate.
UNDER_RARITY_SPOT_CAPS: dict[str, float] = {
    "common": 10.0,
    "uncommon": 30.0,
}

# Identical board-price clusters across unrelated cards (JustTCG poison).
POISON_CLUSTER_MIN_SIZE = 10
POISON_CLUSTER_MIN_SETS = 3
POISON_CLUSTER_MIN_SPOT = 20.0


def _as_positive_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num or num <= 0:  # NaN or non-positive
        return None
    return num


def spot_ratio(new: Any, prior: Any) -> float | None:
    """new / prior when both are positive floats; else None."""
    a = _as_positive_float(new)
    b = _as_positive_float(prior)
    if a is None or b is None:
        return None
    return a / b


def is_absurd_spot_jump(
    new: Any,
    prior: Any,
    *,
    max_ratio: float = SPOT_JUMP_MAX_RATIO,
) -> bool:
    """True when new spot jumped more than ``max_ratio`` vs a known prior."""
    ratio = spot_ratio(new, prior)
    if ratio is None:
        return False
    cap = float(max_ratio)
    if cap <= 1.0:
        return False
    return ratio >= cap or ratio <= (1.0 / cap)


def rarity_spot_cap(rarity: Any) -> float | None:
    key = str(rarity or "").strip().lower()
    if not key:
        return None
    # Match "Rare Holo" etc. only on the leading rarity token for commons/uncommons.
    for token, cap in UNDER_RARITY_SPOT_CAPS.items():
        if key == token or key.startswith(token + " "):
            return float(cap)
    return None


def under_spot_allowed_for_rarity(spot: Any, rarity: Any) -> bool:
    price = _as_positive_float(spot)
    if price is None:
        return False
    cap = rarity_spot_cap(rarity)
    if cap is None:
        return True
    return price <= cap


def under_deal_allowed(
    *,
    spot: Any,
    edge_pct: Any,
    rarity: Any = None,
    price_change_7d_pct: Any = None,
    max_edge_pct: float = RADAR_MAX_UNDER_EDGE_PCT,
    min_spot: float = RADAR_MIN_UNDER_SPOT,
    max_abs_7d_pct: float = RADAR_MAX_ABS_7D_CHANGE_PCT,
) -> bool:
    """Whether an UNDER row is safe to surface on Radar / preview / Deal of Day."""
    price = _as_positive_float(spot)
    if price is None or price < float(min_spot):
        return False

    try:
        edge = float(edge_pct)
    except (TypeError, ValueError):
        return False
    if edge != edge or edge <= 0:
        return False
    if edge > float(max_edge_pct):
        return False

    if not under_spot_allowed_for_rarity(price, rarity):
        return False

    try:
        if price_change_7d_pct is not None:
            chg = float(price_change_7d_pct)
            if chg == chg and abs(chg) > float(max_abs_7d_pct):
                return False
    except (TypeError, ValueError):
        pass

    return True


def _frame_spots(quotes: pd.DataFrame) -> pd.Series:
    price = pd.to_numeric(quotes.get("price"), errors="coerce")
    market = pd.to_numeric(quotes.get("market_price"), errors="coerce")
    spot = price.where(price.notna() & (price > 0), market)
    spot = spot.where(spot > 0)
    return spot.round(2)


def poison_spot_mask(quotes: pd.DataFrame) -> pd.Series:
    """True for rows that share an absurd identical board spot with many peers.

    Triggers when a rounded spot key has ≥ ``POISON_CLUSTER_MIN_SIZE`` cards and
    either the row breaches a rarity spot cap, or the cluster spans
    ≥ ``POISON_CLUSTER_MIN_SETS`` sets at spot ≥ ``POISON_CLUSTER_MIN_SPOT``.
    Cheap bulk commons sharing $0.25 stay clean.
    """
    if quotes is None or quotes.empty:
        return pd.Series(dtype=bool)

    spot_s = _frame_spots(quotes)
    counts = spot_s.value_counts(dropna=True)
    big_keys = {
        float(k)
        for k, n in counts.items()
        if int(n) >= int(POISON_CLUSTER_MIN_SIZE)
    }
    if not big_keys:
        return pd.Series(False, index=quotes.index)

    set_col = (
        quotes["set_name"].fillna("").astype(str).str.strip()
        if "set_name" in quotes.columns
        else pd.Series([""] * len(quotes), index=quotes.index)
    )
    sets_by_key: dict[float, int] = {}
    for key in big_keys:
        member = spot_s == key
        sets_by_key[key] = int(set_col.loc[member & (set_col != "")].nunique())

    rarity_col = (
        quotes["rarity"]
        if "rarity" in quotes.columns
        else pd.Series([None] * len(quotes), index=quotes.index)
    )
    over_cap_flags: list[bool] = []
    multi_flags: list[bool] = []
    for key, rarity in zip(spot_s.tolist(), rarity_col.tolist(), strict=False):
        try:
            key_f = float(key) if key is not None and key == key else None
        except (TypeError, ValueError):
            key_f = None
        if key_f is None or key_f not in big_keys:
            over_cap_flags.append(False)
            multi_flags.append(False)
            continue
        over_cap_flags.append(not under_spot_allowed_for_rarity(key_f, rarity))
        multi_flags.append(
            key_f >= float(POISON_CLUSTER_MIN_SPOT)
            and sets_by_key.get(key_f, 0) >= int(POISON_CLUSTER_MIN_SETS)
        )
    return pd.Series(over_cap_flags, index=quotes.index) | pd.Series(
        multi_flags, index=quotes.index
    )


def summarize_poison_clusters(
    quotes: pd.DataFrame, *, limit: int = 6
) -> list[dict[str, Any]]:
    """Top poisoned spot keys for ops / spot_qa snapshots."""
    mask = poison_spot_mask(quotes)
    if quotes is None or quotes.empty or not bool(mask.any()):
        return []
    poisoned = quotes.loc[mask].copy()
    poisoned = poisoned.assign(_spot=_frame_spots(poisoned))
    rows: list[dict[str, Any]] = []
    for spot, group in poisoned.groupby("_spot", dropna=True):
        rarities = sorted(
            {
                str(r).strip()
                for r in group.get("rarity", pd.Series(dtype=str))
                .dropna()
                .astype(str)
                .tolist()
                if str(r).strip()
            }
        )
        sets = sorted(
            {
                str(s).strip()
                for s in group.get("set_name", pd.Series(dtype=str))
                .dropna()
                .astype(str)
                .tolist()
                if str(s).strip()
            }
        )
        rows.append(
            {
                "price": float(spot),
                "count": int(len(group)),
                "sets": len(sets),
                "rarities": rarities[:6],
            }
        )
    rows.sort(key=lambda r: (-int(r["count"]), -float(r["price"])))
    return rows[: max(0, int(limit))]


def apply_spot_quarantine(quotes: pd.DataFrame) -> pd.DataFrame:
    """Mark poison-cluster rows as not-sure HOLD without dropping them from browse."""
    if quotes is None or quotes.empty:
        return quotes
    out = quotes.copy()
    mask = poison_spot_mask(out)
    out["spot_quarantine"] = mask.astype(bool)
    if not bool(mask.any()):
        return out
    out.loc[mask, "confidence_ok"] = False
    if "confidence_level" in out.columns:
        out.loc[mask, "confidence_level"] = "low"
    else:
        out["confidence_level"] = "medium"
        out.loc[mask, "confidence_level"] = "low"
    if "signal" in out.columns:
        out.loc[mask, "signal"] = SIGNAL_HOLD
    else:
        out["signal"] = SIGNAL_HOLD
    return out

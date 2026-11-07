"""Spot / UNDER deal sanity guards.

JustTCG (and mirrored TCP) spots can land wildly wrong — e.g. bulk commons
stuck at identical high board prices — which then explode conformal UNDER edges.
These helpers gate ingest updates and Radar UNDER surfacing.
"""

from __future__ import annotations

from typing import Any

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

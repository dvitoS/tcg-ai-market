"""Asking match-quality for Soft Ink detail (T0.1).

Maps board quarantine + TCGplayer linkage + history depth to a simple
``high`` / ``med`` / ``low`` badge. This is catalog/spot trust — not AI
forecast confidence.
"""

from __future__ import annotations

import re
from typing import Any, Literal

SpotMatchQuality = Literal["high", "med", "low"]

_TCP_RE = re.compile(r"^\d{4,}$")
_HISTORY_HIGH = 15


def _truthy_quarantine(raw: Any) -> bool:
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        try:
            if raw != raw:  # NaN
                return False
        except Exception:
            return False
        return bool(raw)
    text = str(raw).strip().lower()
    return text in {"1", "true", "yes", "y", "t"}


def _numeric_tcp(raw: Any) -> str | None:
    if raw is None:
        return None
    try:
        if isinstance(raw, float) and raw != raw:
            return None
    except Exception:
        return None
    text = str(raw).strip()
    if not text or text.lower() == "nan":
        return None
    digits = re.sub(r"[^0-9]", "", text)
    if _TCP_RE.match(digits):
        return digits
    return None


def classify_spot_match(
    *,
    tcgplayer_id: str | None,
    spot_quarantine: Any = False,
    history_points: int = 0,
) -> dict[str, Any]:
    """Return ``{quality, reason, tcgplayer_id}`` for detail SSR."""
    tcp = _numeric_tcp(tcgplayer_id)
    quarantined = _truthy_quarantine(spot_quarantine)
    try:
        hist = max(0, int(history_points or 0))
    except (TypeError, ValueError):
        hist = 0

    if quarantined:
        return {
            "quality": "low",
            "reason": "quarantine",
            "tcgplayer_id": tcp,
        }
    if not tcp:
        return {
            "quality": "low",
            "reason": "no_tcp",
            "tcgplayer_id": None,
        }
    if hist < _HISTORY_HIGH:
        return {
            "quality": "med",
            "reason": "thin_history",
            "tcgplayer_id": tcp,
        }
    return {
        "quality": "high",
        "reason": "linked",
        "tcgplayer_id": tcp,
    }
